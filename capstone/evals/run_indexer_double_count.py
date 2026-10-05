# ruff: noqa: E501
"""Why did an edit get processed on two consecutive runs? A timing experiment on the managed indexer.

In the Week 7 controlled test, editing one blob made the next run process 1 document, and the run after
that (nothing changed) process 1 more, before settling at 0. Hypothesis (H1): the indexer re-checks blobs
modified within a short window before the previous run started, so an edit made close to a run is seen
again by the next one. If H1 is right, an edit that is allowed to "age" before the first run should be
processed once, not twice.

This edits one blob in three ways and runs the indexer (no reset) four times after each:

  fresh   edit, then run immediately, then run again immediately, then again after a pause
  aged    edit, WAIT before the first run, then run twice
  none    no edit at all (control): every run should process 0

    uv run --all-groups python capstone/evals/run_indexer_double_count.py [--age 120]

Needs the Week 7 Basic search service with the pipeline built and settled. Writes
`results/indexer_double_count.md|json`. The blob is restored at the end.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from evaluate_chunking import HERE
from run_retrieval import RESULTS

from payments_rag.azure_clients import read_dotenv
from payments_rag.blob_indexing import IndexerNames, documents_from, run_and_wait
from payments_rag.ingestion import ingest

DOC = "faqs"


def main() -> None:
    from azure.identity import DefaultAzureCredential
    from azure.search.documents.indexes import SearchIndexerClient
    from azure.storage.blob import BlobServiceClient

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--age",
        type=int,
        default=120,
        help="seconds to wait between the edit and the first run in the 'aged' case",
    )
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    values = read_dotenv(HERE.parents[1] / ".env")
    credential = DefaultAzureCredential()
    indexer = SearchIndexerClient(values["AZURE_W7_SEARCH_ENDPOINT"], credential)
    box = BlobServiceClient(
        f"https://{values['AZURE_W7_STORAGE_ACCOUNT']}.blob.core.windows.net", credential=credential
    ).get_container_client("corpus")
    names = IndexerNames()
    original = documents_from(ingest())[DOC]

    def run() -> dict[str, Any]:
        r = run_and_wait(indexer, names.indexer, reset=False)
        last = indexer.get_indexer_status(names.indexer).last_result
        return {
            "items": r["items_processed"],
            "seconds": r["seconds"],
            "enumeration_start": str(last.final_tracking_state)[:140],
        }

    def settle() -> None:
        """Run until two consecutive runs process nothing."""
        zero = 0
        while zero < 2:
            zero = zero + 1 if run()["items"] == 0 else 0

    rows: list[dict[str, Any]] = []

    def case(name: str, edit: str | None, wait_before_first_run: int, gaps: list[int]) -> None:
        settle()
        edited_at = None
        if edit is not None:
            box.upload_blob(
                f"{DOC}.md",
                (original + f"\n\nTiming test ({name}): the code word is {edit}.\n").encode(
                    "utf-8"
                ),
                overwrite=True,
            )
            edited_at = time.monotonic()
        time.sleep(wait_before_first_run)
        results = []
        for i, gap in enumerate([0, *gaps], 1):
            time.sleep(gap)
            r = run()
            r["run"] = i
            r["seconds_since_edit"] = (
                None if edited_at is None else round(time.monotonic() - edited_at)
            )
            results.append(r)
            print(
                f"[{name}] run {i}: items={r['items']} (since edit: {r['seconds_since_edit']} s)",
                flush=True,
            )
        rows.append(
            {"case": name, "wait_before_first_run_s": wait_before_first_run, "runs": results}
        )

    case("none (control)", None, 0, [0, 30, 30])
    case("fresh", "pelicanmarble01", 0, [0, 60, 60])
    case("aged", "pelicanmarble02", args.age, [0, 60, 60])

    box.upload_blob(f"{DOC}.md", original.encode("utf-8"), overwrite=True)
    settle()

    lines = [
        f"Items processed by each consecutive incremental run (no reset) on `{DOC}.md`. 'Fresh': the first run starts right after the edit. 'Aged': it starts {args.age} s after.\n",
        "| Case | Wait before run 1 | Run 1 | Run 2 | Run 3 | Run 4 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        cells = " | ".join(
            f"{r['items']} (+{r['seconds_since_edit']} s)"
            if r["seconds_since_edit"] is not None
            else str(r["items"])
            for r in row["runs"]
        )
        lines.append(f"| {row['case']} | {row['wait_before_first_run_s']} s | {cells} |")
    text = "\n".join(lines) + "\n"
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "indexer_double_count.md").write_text(text, encoding="utf-8")
    (RESULTS / "indexer_double_count.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(text)


if __name__ == "__main__":
    main()
