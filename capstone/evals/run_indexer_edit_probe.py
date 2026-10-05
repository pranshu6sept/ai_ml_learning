# ruff: noqa: E501
"""Controlled edit probe for the managed indexer (run on a settled indexer).

Edits one blob, runs the indexer (without a reset) twice, restores the blob, and runs it twice more,
printing how many documents each run processed and what the index holds. Used to check the incremental
behaviour reported in `notes/week-07.md`. Needs the Week 7 Basic search service up, with the pipeline built
and settled (`run_blob_indexer.py`), and `az login`.

    uv run --all-groups python capstone/evals/run_indexer_edit_probe.py
"""

import sys
import time
from collections import Counter

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexerClient
from azure.storage.blob import BlobServiceClient

from payments_rag.azure_clients import read_dotenv
from payments_rag.blob_indexing import documents_from, run_and_wait
from payments_rag.ingestion import ingest

sys.stdout.reconfigure(encoding="utf-8")
v = read_dotenv(r"D:\Coding and AI\AI Engineer Roadmap\.env")
cred = DefaultAzureCredential()
c = SearchIndexerClient(v["AZURE_W7_SEARCH_ENDPOINT"], cred)
s = SearchClient(v["AZURE_W7_SEARCH_ENDPOINT"], "payments-blob-index", cred)
box = BlobServiceClient(
    f"https://{v['AZURE_W7_STORAGE_ACCOUNT']}.blob.core.windows.net", credential=cred
).get_container_client("corpus")
docs = documents_from(ingest())


def per_doc() -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                str(r["doc_id"]).removesuffix(".md")
                for r in s.search("*", select=["doc_id"], top=1000)
            ).items()
        )
    )


def show(label: str, run: dict | None = None) -> None:
    d = per_doc()
    extra = f" items={run['items_processed']} {run['seconds']}s" if run else ""
    print(
        f"{label}:{extra} total={sum(d.values())} faqs={d.get('faqs')} upi={d.get('upi_overview')} card={d.get('card_scheme_public_summary')}",
        flush=True,
    )


show("settled")
box.upload_blob(
    "faqs.md",
    (docs["faqs"] + "\n\nControlled test: the code word is pelicanmarble42.\n").encode("utf-8"),
    overwrite=True,
)
show("edited, before run")
show("run A (edit)", run_and_wait(c, "corpus-indexer", reset=False))
time.sleep(20)
show("20 s later")
show("run B (no change)", run_and_wait(c, "corpus-indexer", reset=False))
hits = {str(r["doc_id"]) for r in s.search("pelicanmarble42", select=["doc_id"], top=5)}
print("marker found in:", hits)
box.upload_blob("faqs.md", docs["faqs"].encode("utf-8"), overwrite=True)
show("run C (restore original)", run_and_wait(c, "corpus-indexer", reset=False))
print(
    "marker still found:",
    {str(r["doc_id"]) for r in s.search("pelicanmarble42", select=["doc_id"], top=5)},
)
show("run D (no change)", run_and_wait(c, "corpus-indexer", reset=False))
