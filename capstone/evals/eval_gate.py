"""The evaluation gate CI runs: fail when golden-set scores drop below the thresholds in gate.json.

    uv run python capstone/evals/eval_gate.py

Two checks, both free and deterministic (no Azure, no model call):

1. Retrieval, recomputed: the offline BM25 retriever over the golden set's answerable questions.
   This catches a change to the corpus, the chunker or the retriever.
2. Answer quality, read from committed results: ``results/generation_*.json`` hold faithfulness,
   correctness and refusal scores from a real model run. The gate compares them with the
   thresholds, and requires the results to carry the *current* prompt version. If a pull
   request edits a prompt, the old results no longer describe it and the gate fails until
   someone re-runs ``run_generation.py`` (it needs Azure) and commits the new results.

What this cannot do: it cannot tell whether committed results were really produced by the code in
the pull request. It enforces "the numbers were refreshed and clear the bar", not "the numbers are
honest"; a reviewer still has to look at the results diff.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluate_chunking import META_SECTIONS, evaluate, load_documents
from run_retrieval import load_golden

from payments_rag import Retriever, strip_sections
from payments_rag.prompts import prompt_version

HERE = Path(__file__).resolve().parent
GATE = HERE / "gate.json"


@dataclass(frozen=True)
class Check:
    name: str
    value: float | None
    minimum: float | None
    passed: bool
    detail: str = ""


def retrieval_scores(strategy: str = "structure_aware") -> dict[str, float]:
    """Offline BM25 (stemmed) scores on the answerable golden questions, like run_retrieval.py."""
    documents = {d: strip_sections(t, META_SECTIONS) for d, t in load_documents().items()}
    golden = load_golden(documents)
    questions = [q for q in golden if q["expected"] in ("answer", "refuse")]
    result = evaluate(
        strategy,
        documents,
        questions,
        retriever_factory=lambda chunks: Retriever(chunks, method="bm25", stem=True),
    )
    return {k: float(v) for k, v in result.items() if isinstance(v, int | float)}


def derived(summary: dict[str, Any]) -> dict[str, float]:
    """The summary's numbers plus the share of unanswerable questions refused."""
    out = {k: float(v) for k, v in summary.items() if isinstance(v, int | float)}
    to_refuse = float(summary.get("to_refuse", 0))
    out["refused_share"] = (
        float(summary.get("correctly_refused", 0)) / to_refuse if to_refuse else 0
    )
    return out


def compare(scores: dict[str, float], minimums: dict[str, float], prefix: str) -> list[Check]:
    checks = []
    for key, minimum in minimums.items():
        value = scores.get(key)
        ok = value is not None and value >= minimum
        detail = "" if value is not None else "metric missing from the results"
        checks.append(Check(f"{prefix}{key}", value, minimum, ok, detail))
    return checks


def check_generation(spec: dict[str, Any], version: str, base: Path = HERE) -> list[Check]:
    path = base / spec["results"]
    name = Path(spec["results"]).name
    if not path.is_file():
        return [Check(f"{name}: results file", None, None, False, "file is missing")]
    data = json.loads(path.read_text(encoding="utf-8"))
    checks = []
    if spec.get("require_current_prompts", True):
        recorded = data.get("prompt_version")
        ok = recorded == version
        detail = (
            ""
            if ok
            else f"results were made with prompts {recorded!r}, the tree has {version!r}; "
            "re-run run_generation.py and commit the new results"
        )
        checks.append(Check(f"{name}: prompt version", None, None, ok, detail))
    checks += compare(derived(data["summary"]), spec["min"], f"{name}: ")
    return checks


def run(gate: dict[str, Any], base: Path = HERE) -> list[Check]:
    checks: list[Check] = []
    retrieval = gate.get("retrieval")
    if retrieval:
        scores = retrieval_scores(retrieval["strategy"])
        checks += compare(scores, retrieval["min"], f"{retrieval['retriever']} retrieval: ")
    version = prompt_version()
    for spec in gate.get("generation", []):
        checks += check_generation(spec, version, base)
    return checks


def main() -> int:
    checks = run(json.loads(GATE.read_text(encoding="utf-8")))
    width = max(len(c.name) for c in checks)
    for c in checks:
        value = "" if c.value is None else f"{c.value:.4f}"
        bar = "" if c.minimum is None else f">= {c.minimum}"
        print(
            f"{'ok  ' if c.passed else 'FAIL'} {c.name:<{width}}  {value:>7}  {bar:<9} {c.detail}"
        )
    failed = [c for c in checks if not c.passed]
    print(
        f"\n{len(checks) - len(failed)} of {len(checks)} checks passed (prompts {prompt_version()})"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
