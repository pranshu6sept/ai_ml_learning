# ruff: noqa: E501
"""Week 11: drift on the assistant's side. Do the questions move, and would we notice retrieval getting worse?

    uv run --group azure --group api python capstone/evals/run_drift.py     # needs az login for embeddings

Two experiments.

1. **Query drift.** The reference is the 48 development questions. Each other set of questions is
   compared with it by (a) the cross-validated AUC of a classifier trying to tell them apart, on real
   Azure OpenAI embeddings, and (b) PSI/KS on question length. A bare AUC means little with sets this
   small, so every observed AUC is read against a NULL: the same measurement between two random,
   non-overlapping halves of the development set (where nothing has drifted).
2. **Retrieval-quality decay, controlled.** The BM25 retriever over the structure-aware chunks is the
   baseline. Then one document at a time is removed from the index (a stand-in for a corpus that has
   gone stale or lost a source). For each removal: Hit@3 on the answerable golden questions, whether
   ``quality_decay`` flags it, and whether a LABEL-FREE signal (PSI/KS of the best retrieval score per
   question) would have noticed without anyone marking answers right or wrong. The questions are the
   same in every run, so input drift is zero by construction.

Limits: 48 reference questions and sets of 9 to 57 are small, hence the null; "different" says the
wording differs, not that quality fell; the removed-document experiment is a simulation of stale data,
not an observation of it; the retriever is the offline BM25 one, not the Azure index.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from evaluate_chunking import META_SECTIONS, chunk_corpus, evaluate, load_documents

from payments_rag import Retriever, strip_sections
from payments_rag.drift import embedding_drift, ks_2samp, psi, quality_decay

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CAP = 24  # rows per side in each classifier draw
DRAWS = 20
TOLERANCE_QUESTIONS = 3  # a drop of 3 questions out of the answerable set counts as decay


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def question_sets() -> dict[str, list[str]]:
    golden = read_jsonl(HERE / "golden_set.jsonl")
    by_split: dict[str, list[str]] = {}
    for row in golden:
        by_split.setdefault(row["split"], []).append(row["question"])
    attacks = [a["text"] for a in read_jsonl(HERE / "adversarial.jsonl") if a["channel"] == "user"]
    attacks += [
        a["text"] for a in read_jsonl(HERE / "adversarial_heldout.jsonl") if a["channel"] == "user"
    ]
    independent = json.loads((HERE / "questions_independent.json").read_text(encoding="utf-8"))
    return {
        "dev": by_split["dev"],
        "heldout": by_split["heldout"],
        "corpus_update": by_split["corpus_update"],
        "independent (web-sourced wording)": [q["question"] for q in independent],
        "abstain (off-topic)": by_split["abstain"],
        "attacks (user channel)": attacks,
        "compound attacks": [a["text"] for a in read_jsonl(HERE / "adversarial_compound.jsonl")],
    }


def auc_against(reference: np.ndarray, other: np.ndarray, draws: int = DRAWS) -> list[float]:
    """AUCs of the classifier between ``reference`` and ``other``, over random draws of at most CAP rows."""
    n = min(CAP, len(other), len(reference))
    out = []
    for seed in range(draws):
        rng = np.random.default_rng(seed)
        a = reference[rng.permutation(len(reference))[:n]]
        b = other[rng.permutation(len(other))[:n]]
        out.append(embedding_drift(a, b, seed=seed).classifier_auc)
    return out


def null_auc(reference: np.ndarray, n: int, draws: int = DRAWS) -> list[float]:
    """The same measurement between two disjoint random halves of the reference (no drift possible)."""
    n = min(n, len(reference) // 2)
    out = []
    for seed in range(draws):
        order = np.random.default_rng(1000 + seed).permutation(len(reference))
        out.append(
            embedding_drift(
                reference[order[:n]], reference[order[n : 2 * n]], seed=seed
            ).classifier_auc
        )
    return out


def length_psi_vs_null(
    ref_len: list[int], lengths: list[int], draws: int = 200
) -> tuple[float, float]:
    """(typical PSI of this set against the reference, 95th percentile of PSI between random draws
    of the same size from the reference itself). PSI grows as samples shrink, so a bare PSI of 2 or 6
    on six questions is not evidence of anything until it is read against that null."""
    n = min(CAP, len(lengths))
    ref = np.asarray(ref_len)
    observed, null = [], []
    for seed in range(draws):
        rng = np.random.default_rng(seed)
        pick = rng.choice(len(lengths), n, replace=False)
        observed.append(psi(ref, np.asarray(lengths)[pick]))
        order = rng.permutation(len(ref))
        null.append(psi(ref[order[n:]], ref[order[:n]]))
    return float(np.mean(observed)), float(np.percentile(null, 95))


def query_drift(embed: Any) -> dict[str, Any]:
    sets = question_sets()
    vectors = {name: np.asarray(embed(texts)) for name, texts in sets.items()}
    reference = vectors["dev"]
    ref_len = [len(q) for q in sets["dev"]]
    rows = []
    for name, vecs in vectors.items():
        if name == "dev":
            continue
        observed = auc_against(reference, vecs)
        null = null_auc(reference, min(CAP, len(vecs)))
        lengths = [len(q) for q in sets[name]]
        statistic, p_value = ks_2samp(ref_len, lengths)
        length_psi_observed, length_psi_null_p95 = length_psi_vs_null(ref_len, lengths)
        rows.append(
            {
                "set": name,
                "n": len(vecs),
                "auc_mean": float(np.mean(observed)),
                "null_auc_mean": float(np.mean(null)),
                "null_auc_p95": float(np.percentile(null, 95)),
                "distinguishable": bool(np.mean(observed) > np.percentile(null, 95)),
                "centroid_cosine_distance": embedding_drift(
                    reference, vecs
                ).centroid_cosine_distance,
                "length_psi": psi(ref_len, lengths),
                "length_psi_same_size": length_psi_observed,
                "length_psi_null_p95": length_psi_null_p95,
                "length_distinguishable": bool(length_psi_observed > length_psi_null_p95),
                "length_ks": statistic,
                "length_ks_p": p_value,
            }
        )
    return {"reference_n": len(reference), "rows": rows}


def top_scores(chunks: list[Any], questions: list[dict[str, Any]]) -> np.ndarray:
    retriever = Retriever(chunks, method="bm25", stem=True)
    scores = []
    for q in questions:
        hits = retriever.search(q["question"], top_k=1)
        scores.append(hits[0].score if hits else 0.0)
    return np.asarray(scores)


def retrieval_decay() -> dict[str, Any]:
    documents = {d: strip_sections(t, META_SECTIONS) for d, t in load_documents().items()}
    golden = read_jsonl(HERE / "golden_set.jsonl")
    questions = [q for q in golden if q["expected"] in ("answer", "refuse")]
    answerable = [q for q in questions if q["expected"] == "answer"]
    factory = lambda chunks: Retriever(chunks, method="bm25", stem=True)  # noqa: E731

    base = evaluate("structure_aware", documents, questions, retriever_factory=factory)
    base_chunks = chunk_corpus(documents, "structure_aware")
    base_scores = top_scores(base_chunks, answerable)
    tolerance = TOLERANCE_QUESTIONS / len(answerable)
    rows = []
    for removed in sorted(documents):
        remaining = {d: t for d, t in documents.items() if d != removed}
        result = evaluate("structure_aware", remaining, questions, retriever_factory=factory)
        scores = top_scores(chunk_corpus(remaining, "structure_aware"), answerable)
        decay = quality_decay(base["hit@3"], result["hit@3"], tolerance)
        ks, _ = ks_2samp(base_scores, scores)
        affected = sum(1 for q in answerable if any(g["doc"] == removed for g in q["gold"]))
        rows.append(
            {
                "removed": removed,
                "questions_with_this_gold_doc": affected,
                "hit_at_3": result["hit@3"],
                "drop": decay.drop,
                "decay_flagged": decay.flagged,
                "top_score_psi": psi(base_scores, scores),
                "top_score_ks": ks,
            }
        )
    return {
        "baseline_hit_at_3": base["hit@3"],
        "answerable": len(answerable),
        "tolerance": tolerance,
        "rows": rows,
    }


def render(result: dict[str, Any]) -> str:
    q, d = result["query_drift"], result["retrieval_decay"]
    lines = [
        "# Week 11: drift on the assistant's side\n",
        "## 1. Do the questions drift? (real embeddings, read against a null)\n",
        f"Reference: the {q['reference_n']} development questions. AUC = how well a classifier tells the set from the reference "
        f"(0.5: it cannot). **Null** = the same measurement between two random halves of the reference, where nothing has moved; "
        f"a set is 'distinguishable' only if its AUC beats the null's 95th percentile. At most {CAP} rows per side, {DRAWS} draws.\n",
        "| Question set | n | AUC | Null AUC (mean / 95th pct) | Distinguishable | Centroid cosine distance | Length PSI (set, same size) | Length PSI null 95th pct | Length distinguishable |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in q["rows"]:
        lines.append(
            f"| {r['set']} | {r['n']} | {r['auc_mean']:.2f} | {r['null_auc_mean']:.2f} / {r['null_auc_p95']:.2f} | "
            f"**{'yes' if r['distinguishable'] else 'no'}** | {r['centroid_cosine_distance']:.4f} | "
            f"{r['length_psi_same_size']:.2f} | {r['length_psi_null_p95']:.2f} | **{'yes' if r['length_distinguishable'] else 'no'}** |"
        )
    lines += [
        "",
        "## 2. Would we notice retrieval quality decaying? (a document removed from the index)\n",
        f"BM25 over structure-aware chunks; baseline Hit@3 = {d['baseline_hit_at_3']:.3f} on {d['answerable']} answerable questions. "
        f"Decay is flagged when Hit@3 falls by more than {d['tolerance']:.3f} (= {TOLERANCE_QUESTIONS} questions). The questions never change, so input drift is zero. "
        "The last two columns are the LABEL-FREE signal: how much the distribution of each question's best retrieval score moved.\n",
        "| Document removed | Questions it answers | Hit@3 | Drop | Quality decay flagged | Best-score PSI | Best-score KS gap |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(d["rows"], key=lambda r: r["drop"], reverse=True):
        lines.append(
            f"| {r['removed']} | {r['questions_with_this_gold_doc']} | {r['hit_at_3']:.3f} | {r['drop']:+.3f} | "
            f"**{'YES' if r['decay_flagged'] else 'no'}** | {r['top_score_psi']:.3f} | {r['top_score_ks']:.3f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    from payments_rag import AzureOpenAIEmbedder, AzureSettings

    embed = AzureOpenAIEmbedder(AzureSettings.from_env())
    result = {"query_drift": query_drift(embed), "retrieval_decay": retrieval_decay()}
    RESULTS.mkdir(exist_ok=True)
    text = render(result)
    (RESULTS / "drift.md").write_text(text, encoding="utf-8")
    (RESULTS / "drift.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
