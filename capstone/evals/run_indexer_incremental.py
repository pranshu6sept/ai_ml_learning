# ruff: noqa: E501
"""How does the managed indexer behave as the corpus changes? (the "incremental" question)

Our push pipeline (`payments_rag.indexing`) rebuilds the whole index every time. The blob indexer tracks
changes, so only changed blobs should be re-processed. This runs the lifecycle on the Week 7 Basic
search service and records, at each step, what the indexer processed and what the index holds:

  1. baseline           full run over the 11 cleaned documents
  2. no change          an incremental run: expect nothing to be processed
  3. edit one blob      append a unique marker word to one document: expect only that blob re-processed
  4. delete a blob      delete another blob (soft delete is on): are its pages removed from the index?
  5. turn on deletion   enable native soft-delete detection on the data source and run again
     detection
  6. undelete           restore the blob: do its pages come back?
  7. schedule           put the indexer on a 5-minute timer, edit a blob, and wait WITHOUT triggering a run

    uv run --all-groups python capstone/evals/run_indexer_incremental.py

Needs the Week 7 stack with the indexer search service on (`infra/week7.bicep`), `az login`, and settings in
`.env`. Takes about 15 to 25 minutes (the schedule step waits for the timer). Writes
`results/indexer_incremental.md|json` and leaves the blobs as the original corpus.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from evaluate_chunking import HERE
from run_retrieval import RESULTS

from payments_rag import AzureSettings
from payments_rag.azure_clients import EMBEDDING_DIMENSIONS, read_dotenv
from payments_rag.blob_indexing import (
    IndexerNames,
    build_pipeline,
    documents_from,
    run_and_wait,
    upload_corpus,
)
from payments_rag.ingestion import ingest

ENV = HERE.parents[1] / ".env"
EDIT_DOC = "faqs"
DELETE_DOC = "card_scheme_public_summary"
SCHEDULE_DOC = "upi_overview"
MARKERS = {"edit": "zebraquartz77", "schedule": "okapijasper88"}


def main() -> None:
    from azure.identity import DefaultAzureCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
    from azure.storage.blob import BlobServiceClient

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    values = read_dotenv(ENV)
    endpoint, account = values["AZURE_W7_SEARCH_ENDPOINT"], values["AZURE_W7_STORAGE_ACCOUNT"]
    settings = AzureSettings.from_env()
    credential = DefaultAzureCredential()
    names = IndexerNames()
    documents = documents_from(ingest())
    container = BlobServiceClient(
        f"https://{account}.blob.core.windows.net", credential=credential
    ).get_container_client("corpus")
    index_client, indexer_client = (
        SearchIndexClient(endpoint, credential),
        SearchIndexerClient(endpoint, credential),
    )
    search = SearchClient(endpoint, names.index, credential)

    def build(**options: Any) -> None:
        build_pipeline(
            index_client,
            indexer_client,
            names=names,
            storage_resource_id=values["AZURE_W7_STORAGE_RESOURCE_ID"],
            identity_resource_id=values.get("AZURE_W7_INDEXER_IDENTITY_ID"),
            container="corpus",
            openai_endpoint=settings.openai_endpoint,
            embedding_deployment=settings.embedding_deployment,
            dimensions=EMBEDDING_DIMENSIONS,
            **options,
        )

    def pages() -> Counter[str]:
        return Counter(
            str(r["doc_id"]).removesuffix(".md")
            for r in search.search(search_text="*", select=["doc_id"], top=1000)
        )

    def found(marker: str) -> list[str]:
        return sorted(
            {
                str(r["doc_id"]).removesuffix(".md")
                for r in search.search(search_text=marker, select=["doc_id"], top=5)
            }
            if marker
            else []
        )

    steps: list[dict[str, Any]] = []

    def record(step: str, change: str, run: dict[str, Any] | None, **extra: Any) -> None:
        counts = pages()
        row = {
            "step": step,
            "change": change,
            "indexer_items": None if run is None else run["items_processed"],
            "indexer_status": None if run is None else run["status"],
            "seconds": None if run is None else run["seconds"],
            "pages_total": sum(counts.values()),
            "pages_faqs": counts.get(EDIT_DOC, 0),
            "pages_card_scheme": counts.get(DELETE_DOC, 0),
            "pages_upi": counts.get(SCHEDULE_DOC, 0),
            **extra,
        }
        steps.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    # 1. baseline
    upload_corpus(account, "corpus", documents, credential)
    build()
    record(
        "1 baseline (reset + full run)", "11 documents", run_and_wait(indexer_client, names.indexer)
    )

    # 2. nothing changed
    record("2 no change", "none", run_and_wait(indexer_client, names.indexer, reset=False))

    # 3. edit one blob
    container.upload_blob(
        f"{EDIT_DOC}.md",
        (
            documents[EDIT_DOC] + f"\n\nIncremental test: the code word is {MARKERS['edit']}.\n"
        ).encode("utf-8"),
        overwrite=True,
    )
    run = run_and_wait(indexer_client, names.indexer, reset=False)
    record(
        "3 edit one blob",
        f"appended a sentence to {EDIT_DOC}.md",
        run,
        marker_found_in=found(MARKERS["edit"]),
    )

    # 4. delete a blob, no deletion detection yet
    container.delete_blob(f"{DELETE_DOC}.md")
    record(
        "4 delete a blob (no detection policy)",
        f"deleted {DELETE_DOC}.md",
        run_and_wait(indexer_client, names.indexer, reset=False),
    )

    # 5. enable deletion detection
    build(soft_delete=True)
    record(
        "5 enable soft-delete detection, run",
        "data source updated",
        run_and_wait(indexer_client, names.indexer, reset=False),
    )

    # 6. undelete
    container.get_blob_client(f"{DELETE_DOC}.md").undelete_blob()
    record(
        "6 undelete the blob",
        f"restored {DELETE_DOC}.md",
        run_and_wait(indexer_client, names.indexer, reset=False),
    )

    # 7. schedule: edit a blob and wait for the timer, never calling run
    build(soft_delete=True, schedule_minutes=5)
    before = indexer_client.get_indexer_status(names.indexer).last_result
    before_start = before.start_time if before is not None else None
    edited_at = datetime.now(UTC)
    container.upload_blob(
        f"{SCHEDULE_DOC}.md",
        (
            documents[SCHEDULE_DOC]
            + f"\n\nScheduled test: the code word is {MARKERS['schedule']}.\n"
        ).encode("utf-8"),
        overwrite=True,
    )
    waited = None
    deadline = time.monotonic() + 600
    scheduled: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        time.sleep(15)
        last = indexer_client.get_indexer_status(names.indexer).last_result
        if (
            last is not None
            and last.start_time != before_start
            and last.status in ("success", "transientFailure", "persistentFailure")
            and last.item_count >= 1
        ):
            waited = round((datetime.now(UTC) - edited_at).total_seconds())
            scheduled = {
                "status": last.status,
                "items_processed": last.item_count,
                "seconds": waited,
            }
            break
    record(
        "7 scheduled run (every 5 minutes), no manual trigger",
        f"appended a sentence to {SCHEDULE_DOC}.md",
        scheduled,
        marker_found_in=found(MARKERS["schedule"]),
        waited_s=waited,
    )

    # leave storage and the schedule as they were
    build(soft_delete=True)
    upload_corpus(account, "corpus", documents, credential)

    lines = [
        "Lifecycle of the managed indexer on the Week 7 Basic search service (one run of the script; 11 documents, 44 pages at baseline).\n",
        "| Step | Change | Documents the indexer processed | Pages in index | pages of faqs / card scheme / upi | Extra |",
        "|---|---|---|---|---|---|",
    ]
    for s in steps:
        extra = ", ".join(f"{k}={s[k]}" for k in ("marker_found_in", "waited_s") if k in s)
        lines.append(
            f"| {s['step']} | {s['change']} | {s['indexer_items'] if s['indexer_items'] is not None else 'no run seen'} | {s['pages_total']} | {s['pages_faqs']} / {s['pages_card_scheme']} / {s['pages_upi']} | {extra} |"
        )
    text = "\n".join(lines) + "\n"
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "indexer_incremental.md").write_text(text, encoding="utf-8")
    (RESULTS / "indexer_incremental.json").write_text(
        json.dumps(steps, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(text)


if __name__ == "__main__":
    main()
