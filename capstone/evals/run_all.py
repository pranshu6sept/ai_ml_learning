"""Run the whole evaluation with one command and write the results to ``results/``.

    uv run --all-groups python capstone/evals/run_all.py            # offline: free, about a minute
    uv run --all-groups python capstone/evals/run_all.py --azure    # also Azure retrieval + answers

Steps, each stopping the run if it fails:
  1. check that ``golden_set.jsonl`` is up to date with the question files and reference answers;
  2. retrieval metrics on the golden set (recall@k, MRR, nDCG for every chunking strategy and
     local retriever; with ``--azure`` also the Azure index, with and without the semantic ranker);
  3. with ``--azure`` only: the real pipeline on every golden question, judged for faithfulness,
     relevance and correctness (about 25 minutes at the deployment's rate limit; resumable).

Results are written as ``results/retrieval.md|json`` and ``results/generation.md|json``. The
generation step needs ``az login`` and the deployed Azure resources (``infra/deploy.ps1``).
"""

from __future__ import annotations

import argparse
import json
import sys

import build_golden_set
import run_generation
import run_retrieval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--azure", action="store_true", help="include the steps that call Azure")
    args = parser.parse_args(argv)

    expected = "\n".join(json.dumps(e, ensure_ascii=False) for e in build_golden_set.build()) + "\n"
    if build_golden_set.OUT.read_text(encoding="utf-8") != expected:
        print("golden_set.jsonl is out of date: run build_golden_set.py and commit the result")
        return 1
    print("step 1/3: golden set is up to date")

    print("step 2/3: retrieval metrics" + (" (including Azure)" if args.azure else " (offline)"))
    run_retrieval.main(["--azure"] if args.azure else [])

    if args.azure:
        print("step 3/3: answer quality on Azure")
        run_generation.main([])
    else:
        print("step 3/3: skipped (needs --azure)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
