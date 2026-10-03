from __future__ import annotations

import json
from pathlib import Path

from payments_rag.chunking import compare_chunking_strategies

TEXT = """# Payment lifecycle
Authorization checks whether the card is valid.

Settlement moves funds after processing.

## Disputes
A dispute happens when a customer challenges a transaction."""


def main() -> None:
    summary = compare_chunking_strategies(
        TEXT,
        chunk_size=8,
        overlap=2,
        max_chunk_size=8,
    )
    out_path = Path(__file__).with_name("chunking_summary.json")
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved chunking summary to {out_path}")


if __name__ == "__main__":
    main()
