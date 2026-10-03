# ruff: noqa: E501
"""Does the system answer from the evidence? End to end on Azure, on all 80 questions.

Pipeline per question: Azure hybrid search (10 candidates) -> local cross-encoder rerank -> top 3 passages
-> gpt-4.1-mini with the cited-answer prompt -> a judge model (the same deployment) checks the answer against
the passages. Two operating points come from the same generations:

* no gate: always answer, so we see whether the model refuses on its own when the passages don't help;
* gated: refuse when the best reranked score is below a threshold chosen on the tune set only.

Limits to keep in mind: the judge is the same model that wrote the answers, so its verdicts are imperfect (read
the flagged answers); the questions are my own; one run. The search index must already hold the corpus (run
evaluate_azure.py or azure_smoke_test.py first). Calls are paced to stay under the deployment's token limit.

Run:  uv run --all-groups python capstone/evals/evaluate_grounding.py
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from collections.abc import Callable
from functools import partial
from typing import Any

import numpy as np
from evaluate_chunking import HERE, META_SECTIONS, is_relevant, load_documents, load_questions

from payments_rag import (
    NO_ANSWER,
    AzureChatGenerator,
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    CrossEncoderReranker,
    GroundedAnswer,
    build_prompt,
    choose_threshold,
    rerank,
    strip_sections,
)

STRATEGY = "structure_aware"
CANDIDATES = 10
TOP_K = 3
TPM_BUDGET = 7000  # stay under the deployment's 10,000 tokens-per-minute limit
MAX_REQUESTS_PER_MINUTE = 25  # and under its request-per-minute limit (a 429 hit at about 60+)
NO_SCORE = -20.0
CACHE = HERE / "grounding_cache.json"  # finished questions, so a failed run can resume
COMPUTED_KEYS = (
    "top_score",
    "evidence",
    "evidence_has_answer",
    "ms",
    "reply",
    "model_refused",
    "citations",
    "judgement",
)


class Pacer:
    """Waits as needed so that, in any 60-second window, estimated tokens and request count stay
    under their budgets. (The deployment limits both; short refusals can hit the request limit.)"""

    def __init__(self, token_budget: int, max_requests: int) -> None:
        self.token_budget = token_budget
        self.max_requests = max_requests
        self.events: deque[tuple[float, int]] = deque()

    def wait(self, tokens: int) -> None:
        while True:
            now = time.monotonic()
            while self.events and now - self.events[0][0] > 60:
                self.events.popleft()
            within_tokens = sum(t for _, t in self.events) + tokens <= self.token_budget
            if not self.events or (within_tokens and len(self.events) < self.max_requests):
                break
            time.sleep(max(0.5, 60 - (now - self.events[0][0]) + 0.2))
        self.events.append((time.monotonic(), tokens))


def call_with_retries(call: Callable[[], str], attempts: int = 6) -> str:
    """Run an Azure OpenAI call, waiting and retrying when the service answers 429 (rate limited)."""
    import openai

    for attempt in range(attempts):
        try:
            return call()
        except openai.RateLimitError:
            if attempt == attempts - 1:
                raise
            wait = 20 * (attempt + 1)
            print(f"      rate limited; waiting {wait} s", flush=True)
            time.sleep(wait)
    raise AssertionError("unreachable")


def estimate_tokens(text: str) -> int:
    return len(text) // 3 + 350  # conservative input estimate plus room for the reply


def is_refusal(reply: str) -> bool:
    return reply.strip().lower().startswith("i don't know")


def citation_stats(reply: str, n_evidence: int) -> dict[str, Any]:
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", reply) if s.strip()]
    marks = [int(m) for m in re.findall(r"\[(\d+)\]", reply)]
    return {
        "has_citation": bool(marks),
        "valid_indexes": bool(marks) and all(1 <= m <= n_evidence for m in marks),
        "sentences": len(sentences),
        "sentences_cited": sum(bool(re.search(r"\[\d+\]", s)) for s in sentences),
    }


JUDGE_PROMPT = """You are a strict fact-checker. Below are numbered passages, a question, and an ANSWER that was written from the passages.

Question: {question}

Passages:
{passages}

ANSWER:
{reply}
{reference}
Return a JSON object with these keys:
- "supported": true only if EVERY factual claim in the ANSWER is stated in the passages above. A claim that comes from general knowledge and is not in the passages counts as unsupported.
- "citations_correct": true only if every [n] in the ANSWER points to a passage that actually states the claim it follows, and no claim lacks a citation.
- "correct": {correct_hint}
- "unsupported_claims": a list of the claims you judged unsupported (empty if there are none).
"""


def judge(
    generator: AzureChatGenerator, pacer: Pacer, item: dict[str, Any], passages: str, reply: str
) -> dict[str, Any]:
    if item["answerable"]:
        facts = "\n".join(f"- {g['phrase']}" for g in item["gold"])
        reference = f"\nReference facts (a correct answer states at least one of these):\n{facts}\n"
        hint = "true if the ANSWER states one of the reference facts and does not contradict it, otherwise false"
    else:
        reference, hint = "", "null (there is no reference for this question)"
    prompt = JUDGE_PROMPT.format(
        question=item["question"],
        passages=passages,
        reply=reply,
        reference=reference,
        correct_hint=hint,
    )
    pacer.wait(estimate_tokens(prompt))
    raw = call_with_retries(partial(generator.complete, prompt, json_mode=True))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"judge_error": raw[:200]}
    return {
        "supported": bool(data.get("supported")),
        "citations_correct": bool(data.get("citations_correct")),
        "correct": data.get("correct"),
        "unsupported_claims": list(data.get("unsupported_claims") or []),
    }


def pct(num: int, den: int) -> str:
    return f"{num}/{den} ({num / den:.0%})" if den else "n/a"


def main() -> None:
    settings = AzureSettings.from_env()
    embedder = AzureOpenAIEmbedder(settings)
    store = AzureSearchStore(settings)
    retriever = AzureHybridRetriever(store, embedder, STRATEGY)
    if not retriever.search("card payment", 1):
        raise SystemExit(
            "The search index is empty. Run evaluate_azure.py or azure_smoke_test.py first."
        )
    reranker = CrossEncoderReranker()
    generator = AzureChatGenerator(settings)
    pacer = Pacer(TPM_BUDGET, MAX_REQUESTS_PER_MINUTE)
    cache: dict[str, Any] = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    docs = {n: strip_sections(t, META_SECTIONS) for n, t in load_documents().items()}
    items: list[dict[str, Any]] = []
    for split, path in (("tune", "questions.json"), ("test", "questions_heldout.json")):
        items += [{**q, "split": split} for q in load_questions(docs, HERE / path)]
    items += load_questions(docs, HERE / "questions_abstain.json")
    for q in items:
        q["answerable"] = bool(q["gold"])

    for n, item in enumerate(items, 1):
        saved = cache.get(item["id"])
        if saved and saved["question"] == item["question"]:
            item.update(saved["fields"])  # finished in an earlier run: reuse it
            print(f"{n:2d}/{len(items)} {item['id']:>4} (cached)", flush=True)
            continue
        t0 = time.perf_counter()
        candidates = retriever.search(item["question"], CANDIDATES)
        t1 = time.perf_counter()
        ranked = rerank(item["question"], candidates, reranker)
        t2 = time.perf_counter()
        evidence = tuple(ranked[:TOP_K])
        item["top_score"] = ranked[0].score if ranked else NO_SCORE
        item["evidence"] = [f"{h.chunk.doc_id} > {h.chunk.section}" for h in evidence]
        item["evidence_has_answer"] = item["answerable"] and any(
            is_relevant(h.chunk, item) for h in evidence
        )
        item["ms"] = {"retrieve": (t1 - t0) * 1000, "rerank": (t2 - t1) * 1000}

        if not evidence:
            item["reply"], item["ms"]["generate"] = NO_ANSWER, 0.0
        else:
            answer = GroundedAnswer(item["question"], False, evidence, "always answer")
            pacer.wait(estimate_tokens(build_prompt(answer)))
            t3 = time.perf_counter()
            item["reply"] = call_with_retries(partial(generator.generate, answer))
            item["ms"]["generate"] = (time.perf_counter() - t3) * 1000
        item["model_refused"] = is_refusal(item["reply"])
        item["citations"] = citation_stats(item["reply"], len(evidence))
        item["judgement"] = None
        if evidence and not item["model_refused"]:
            passages = "\n\n".join(f"[{i}] {h.chunk.text}" for i, h in enumerate(evidence, 1))
            item["judgement"] = judge(generator, pacer, item, passages, item["reply"])
        cache[item["id"]] = {
            "question": item["question"],
            "fields": {k: item[k] for k in COMPUTED_KEYS},
        }
        CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        print(
            f"{n:2d}/{len(items)} {item['id']:>4} score {item['top_score']:6.2f}  "
            f"{'refused' if item['model_refused'] else 'answered'}",
            flush=True,
        )

    # ---- threshold: tuned on the tune set only, then applied everywhere
    tune = [q for q in items if q["split"] == "tune"]
    threshold = choose_threshold(
        [q["top_score"] for q in tune if q["answerable"]],
        [q["top_score"] for q in tune if not q["answerable"]],
    )
    for q in items:
        q["gate_passed"] = q["top_score"] >= threshold
        q["shipped_refusal"] = (not q["gate_passed"]) or q["model_refused"]

    def part(split: str | None) -> list[dict[str, Any]]:
        return [q for q in items if split is None or q["split"] == split]

    def good(q: dict[str, Any], key: str) -> bool:
        return bool(q["judgement"]) and q["judgement"].get(key) is True

    lines = [
        "Azure hybrid retrieval -> local reranker -> `gpt-4.1-mini` with the cited prompt; the same deployment judges.",
        f"80 questions: {sum(q['answerable'] for q in items)} answerable, {sum(not q['answerable'] for q in items)} unanswerable. "
        f"Gate threshold {threshold:.2f} (reranker score), chosen on the tune set only.\n",
        "## 1. No gate: does the model refuse on its own?\n",
        "| | Answerable (model answered / refused) | Answered correctly | Unanswerable (model refused / answered) |",
        "|---|---|---|---|",
    ]
    for label, split in (("All questions", None), ("Tune set", "tune"), ("Test set", "test")):
        a = [q for q in part(split) if q["answerable"]]
        u = [q for q in part(split) if not q["answerable"]]
        answered = [q for q in a if not q["model_refused"]]
        lines.append(
            f"| {label} | {len(answered)} / {len(a) - len(answered)} | {pct(sum(good(q, 'correct') for q in answered), len(answered))} "
            f"| {sum(q['model_refused'] for q in u)} / {sum(not q['model_refused'] for q in u)} |"
        )

    answered_all = [
        q for q in items if q["judgement"] is not None and "judge_error" not in q["judgement"]
    ]
    cites = [q["citations"] for q in answered_all]
    lines += [
        "\n## 2. Quality of the answers the model gave (no gate)\n",
        f"Judged answers: {len(answered_all)} (judge errors: {sum('judge_error' in (q['judgement'] or {}) for q in items)}).\n",
        "| Check | Result |",
        "|---|---|",
        f"| Every claim supported by the passages (judge) | {pct(sum(good(q, 'supported') for q in answered_all), len(answered_all))} |",
        f"| Citations point to the passage that states the claim (judge) | {pct(sum(good(q, 'citations_correct') for q in answered_all), len(answered_all))} |",
        f"| Answer has at least one [n] citation | {pct(sum(c['has_citation'] for c in cites), len(cites))} |",
        f"| Every [n] is a valid passage number | {pct(sum(c['valid_indexes'] for c in cites), len(cites))} |",
        f"| Sentences carrying a citation | {pct(sum(c['sentences_cited'] for c in cites), sum(c['sentences'] for c in cites))} |",
    ]

    a_answered = [q for q in answered_all if q["answerable"]]
    with_ev = [q for q in a_answered if q["evidence_has_answer"]]
    without_ev = [q for q in a_answered if not q["evidence_has_answer"]]
    lines += [
        "\n## 3. Is a wrong answer a retrieval problem or a generation problem? (answerable, answered)\n",
        "| Retrieved passages contain the answer? | Questions | Answered correctly |",
        "|---|---|---|",
        f"| Yes | {len(with_ev)} | {pct(sum(good(q, 'correct') for q in with_ev), len(with_ev))} |",
        f"| No | {len(without_ev)} | {pct(sum(good(q, 'correct') for q in without_ev), len(without_ev))} |",
        "\n## 4. With the gate (what a user would actually see)\n",
        "| | Answerable: answered / correct | Answerable refused | Unanswerable refused | Unanswerable answered (wrong answers shipped) |",
        "|---|---|---|---|---|",
    ]
    for label, split in (
        ("All questions", None),
        ("Tune set (threshold fitted here)", "tune"),
        ("Test set (threshold not fitted here)", "test"),
    ):
        a = [q for q in part(split) if q["answerable"]]
        u = [q for q in part(split) if not q["answerable"]]
        shipped = [q for q in a if not q["shipped_refusal"]]
        lines.append(
            f"| {label} | {len(shipped)} / {sum(good(q, 'correct') for q in shipped)} | {len(a) - len(shipped)} "
            f"| {sum(q['shipped_refusal'] for q in u)} | {sum(not q['shipped_refusal'] for q in u)} |"
        )

    ms = {
        k: float(np.mean([q["ms"][k] for q in items if q["ms"].get(k)]))
        for k in ("retrieve", "rerank", "generate")
    }
    lines += [
        "\n## 5. Time per question (this laptop to Azure)\n",
        f"Retrieve (embed + search, two regions) {ms['retrieve']:.0f} ms; rerank (local CPU) {ms['rerank']:.0f} ms; "
        f"generate {ms['generate']:.0f} ms.\n",
        "## 6. Answers to read (judge says unsupported or incorrect, or a refusal that should not have happened)\n",
    ]
    flagged = [
        q
        for q in answered_all
        if not good(q, "supported") or (q["answerable"] and not good(q, "correct"))
    ] + [q for q in items if q["answerable"] and q["model_refused"]]
    for q in flagged:
        verdict = q["judgement"] or {}
        lines.append(
            f"- **{q['id']}** ({'answerable' if q['answerable'] else 'unanswerable'}; evidence has answer: "
            f"{q['evidence_has_answer']}; score {q['top_score']:.2f}): {q['question']}\n"
            f"  - Reply: {q['reply'][:300].replace(chr(10), ' ')}\n"
            f"  - Judge: supported={verdict.get('supported')}, correct={verdict.get('correct')}, "
            f"claims={verdict.get('unsupported_claims')}"
        )
    text = "\n".join(lines) + "\n"
    (HERE / "grounding_eval.json").write_text(
        json.dumps({"threshold": threshold, "items": items}, indent=2, default=str),
        encoding="utf-8",
    )
    (HERE / "grounding_eval.md").write_text(text, encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    main()
