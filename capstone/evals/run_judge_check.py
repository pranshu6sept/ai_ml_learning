# ruff: noqa: E501
"""Cross-check the answer judge with a model that did not write the answers.

`run_generation.py` graded answers with the same deployment that wrote them (gpt-4.1-mini). Here a
different model (the `AZURE_OPENAI_JUDGE_DEPLOYMENT`, gpt-5-mini) re-grades the same answers with the
same prompts and the same retrieved passages, and we compare the two judges:

* how often they agree, as raw agreement and Cohen's kappa (agreement corrected for chance);
* what each judge's mean scores are;
* which answers they disagree on, to be read by hand.

Needs `generation_cache.json` (run `run_generation.py` first). Nothing is regenerated: only the
judging is repeated. Finished gradings are cached in `judge_check_cache.json`, so a failed run resumes.
Calls are paced for the judge deployment's token limit.

    uv run --all-groups python capstone/evals/run_judge_check.py [--limit N]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from typing import Any

from evaluate_chunking import HERE
from evaluate_grounding import Pacer, call_with_retries, estimate_tokens
from pydantic import BaseModel
from run_generation import judge
from run_retrieval import RESULTS

from payments_rag import AzureChatGenerator, AzureSettings, agreement
from payments_rag.azure_clients import read_dotenv

GENERATION_CACHE = HERE / "generation_cache.json"
TPM_BUDGET = 20000  # the judge deployment allows 30,000 tokens per minute; reasoning needs headroom
MAX_REQUESTS_PER_MINUTE = 40


class PacedJudge(AzureChatGenerator):
    def __init__(
        self, settings: AzureSettings, pacer: Pacer, temperature: float | None = None
    ) -> None:
        super().__init__(settings, temperature=temperature, deployment=settings.judge_deployment)
        self._pacer = pacer
        self.waited = 0.0

    def complete(
        self, prompt: str, *, json_mode: bool = False, schema: type[BaseModel] | None = None
    ) -> str:
        self._pacer.wait(estimate_tokens(prompt) * 3)  # allow for the model's hidden reasoning
        return call_with_retries(
            lambda: super(PacedJudge, self).complete(prompt, json_mode=json_mode, schema=schema)
        )


def label_faithfulness(j: dict[str, Any] | None) -> str:
    """'supported' when every claim is supported, 'unsupported' when any is not, 'none' if unusable."""
    if not j or j["score"] is None:
        return "none"
    return "supported" if j["score"] == 1.0 else "unsupported"


def label_verdict(j: dict[str, Any] | None) -> str:
    return "none" if not j else str(j["verdict"])


def mean(values: list[float]) -> float:
    defined = [v for v in values if not math.isnan(v)]
    return sum(defined) / len(defined) if defined else float("nan")


def fmt(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.2f}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="only the first N answered questions")
    parser.add_argument(
        "--foundry-deployment",
        help="judge with this deployment on the Foundry resource (a non-OpenAI model), "
        "read from AZURE_W7_FOUNDRY_ENDPOINT in .env",
    )
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    records = [
        r for r in json.loads(GENERATION_CACHE.read_text("utf-8")).values() if not r["refused"]
    ]
    if args.limit:
        records = records[: args.limit]
    settings = AzureSettings.from_env()
    suffix = ""
    if args.foundry_deployment:
        endpoint = read_dotenv(HERE.parents[1] / ".env")["AZURE_W7_FOUNDRY_ENDPOINT"]
        settings = dataclasses.replace(
            settings, openai_endpoint=endpoint, judge_deployment=args.foundry_deployment
        )
        suffix = f"_{args.foundry_deployment}"
        pacer = Pacer(
            12000, 15
        )  # the Foundry deployments allow 20 requests and 20K tokens a minute
        temperature: float | None = 0.0  # not a reasoning model: temperature 0 is accepted
    else:
        pacer = Pacer(TPM_BUDGET, MAX_REQUESTS_PER_MINUTE)
        temperature = None
    if not settings.judge_deployment:
        raise SystemExit("AZURE_OPENAI_JUDGE_DEPLOYMENT is not set (see .env.example)")
    judge_chat = PacedJudge(settings, pacer, temperature)
    cache_path = HERE / f"judge_check_cache{suffix}.json"
    cache: dict[str, Any] = json.loads(cache_path.read_text("utf-8")) if cache_path.exists() else {}

    second: dict[str, dict[str, Any]] = {}
    for n, r in enumerate(records, 1):
        key = r["id"]
        cached = cache.get(key)
        if (
            cached
            and cached["reply"] == r["reply"]
            and cached["judge"] == settings.judge_deployment
        ):
            second[key] = cached["judgements"]
            continue
        judgements = judge(judge_chat, r, r["reference_answer"])  # type: ignore[arg-type]
        cache[key] = {
            "reply": r["reply"],
            "judge": settings.judge_deployment,
            "judgements": judgements,
        }
        cache_path.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
        second[key] = judgements
        print(f"[{n}/{len(records)}] {key} judged", flush=True)

    rows = []
    for name, label in (
        ("faithfulness (all claims supported or not)", label_faithfulness),
        ("relevance (direct / partial / off_topic)", label_verdict),
        ("correctness (correct / partial / incorrect)", label_verdict),
    ):
        kind = name.split(" ")[0]
        first = [label(r["judgements"].get(kind)) for r in records]
        other = [label(second[r["id"]].get(kind)) for r in records]
        observed, kappa = agreement(first, other)
        rows.append((name, kind, observed, kappa, first, other))

    def scores(kind: str, source: list[dict[str, Any]]) -> list[float]:
        out = []
        for j in source:
            item = j.get(kind)
            out.append(float("nan") if not item or item["score"] is None else item["score"])
        return out

    first_j = [r["judgements"] for r in records]
    second_j = [second[r["id"]] for r in records]
    lines = [
        f"{len(records)} answers given in the generation run, re-graded by `{settings.judge_deployment}` "
        "(a different model from the one that wrote them, `gpt-4.1-mini`) with the same prompts and "
        "passages. Same questions, same answers: only the judge changes. One run.\n",
        "## Agreement between the two judges\n",
        "| What was judged | Raw agreement | Cohen's kappa |",
        "|---|---|---|",
    ]
    for name, _kind, observed, kappa, _f, _o in rows:
        lines.append(f"| {name} | {fmt(observed)} | {fmt(kappa)} |")
    lines += [
        "",
        "Kappa corrects agreement for chance (1 = perfect, 0 = no better than chance, n/a = both judges use one label for everything: read the raw number). "
        "When almost every answer gets the top label, kappa is unstable and a few disagreements move it a lot.\n",
        "## Mean scores by judge\n",
        "| Measure | gpt-4.1-mini (answering model) | "
        + settings.judge_deployment
        + " (different model) |",
        "|---|---|---|",
    ]
    for kind in ("faithfulness", "relevance", "correctness"):
        lines.append(
            f"| {kind} | {fmt(mean(scores(kind, first_j)))} | {fmt(mean(scores(kind, second_j)))} |"
        )
    lines += ["", "## Answers where the judges disagree (read by hand)\n"]
    disagreements = 0
    for r in records:
        notes = []
        for _name, kind, _o, _k, first, other in rows:
            i = records.index(r)
            if first[i] != other[i]:
                detail = ""
                if kind == "faithfulness":
                    one = (r["judgements"].get(kind) or {}).get("unsupported", "n/a")
                    two = (second[r["id"]].get(kind) or {}).get("unsupported", "n/a")
                    detail = f"; unsupported claims per gpt-4.1-mini: {one}, per {settings.judge_deployment}: {two}"
                notes.append(f"{kind}: {first[i]} vs {other[i]}{detail}")
        if notes:
            disagreements += 1
            lines.append(
                f"- {r['id']} ({'; '.join(notes)}): {r['question']}\n  answer: {r['reply']}"
            )
    if not disagreements:
        lines.append("none")
    text = "\n".join(lines) + "\n"
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"judge_check{suffix}.md").write_text(text, encoding="utf-8")
    (RESULTS / f"judge_check{suffix}.json").write_text(
        json.dumps(
            {
                "judge": settings.judge_deployment,
                "n": len(records),
                "agreement": {kind: {"raw": o, "kappa": k} for _n, kind, o, k, _f, _x in rows},
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(text)


if __name__ == "__main__":
    main()
