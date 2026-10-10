"""The prompts the assistant sends to the model, kept as text files so a change shows in a diff.

Each file is a template filled with ``str.format``. ``prompt_version()`` is a short hash of every
prompt file; evaluation results record it, and `capstone/evals/eval_gate.py` fails when the
committed results were produced by different prompts than the ones in the tree.
"""

from __future__ import annotations

import hashlib
from importlib import resources

_PACKAGE = "payments_rag.prompts"


def load(name: str) -> str:
    """The text of ``<name>.txt``, exactly as stored (a single final newline included)."""
    return resources.files(_PACKAGE).joinpath(f"{name}.txt").read_text(encoding="utf-8")


def prompt_names() -> list[str]:
    return sorted(
        p.name.removesuffix(".txt")
        for p in resources.files(_PACKAGE).iterdir()
        if p.name.endswith(".txt")
    )


def prompt_version() -> str:
    """12 hex characters identifying the exact text of all prompt files (names and contents)."""
    digest = hashlib.sha256()
    for name in prompt_names():
        digest.update(name.encode() + b"\0" + load(name).encode("utf-8") + b"\0")
    return digest.hexdigest()[:12]
