"""Build the zip that App Service runs: the `payments_rag` package plus `requirements.txt`.

    uv run python capstone/deploy/build_zip.py            # writes capstone/deploy/dist/app.zip

The zip holds only the package source and the compiled requirements: no `.env`, no tests, no
evaluation data, no caches, no notebooks. App Service builds the Python environment from
`requirements.txt` when the zip is deployed (`SCM_DO_BUILD_DURING_DEPLOYMENT=true` in
`infra/week8.bicep`).
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "src" / "payments_rag"
REQUIREMENTS = HERE / "requirements.txt"
OUT = HERE / "dist" / "app.zip"
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def package_files(source: Path = SOURCE) -> list[Path]:
    """Every source file of the package, sorted, without caches."""
    return sorted(
        p
        for p in source.rglob("*")
        if p.is_file()
        and not (set(p.relative_to(source).parts[:-1]) & SKIP_DIRS)
        and p.suffix not in SKIP_SUFFIXES
    )


def build(out: Path = OUT, source: Path = SOURCE, requirements: Path = REQUIREMENTS) -> list[str]:
    """Write the zip and return the names it contains."""
    if not requirements.exists():
        raise FileNotFoundError(f"{requirements} is missing; compile it from requirements.in first")
    out.parent.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(requirements, "requirements.txt")
        names.append("requirements.txt")
        for path in package_files(source):
            name = f"{source.name}/{path.relative_to(source).as_posix()}"
            archive.write(path, name)
            names.append(name)
    return names


if __name__ == "__main__":
    contents = build()
    print(f"wrote {OUT} with {len(contents)} files ({OUT.stat().st_size // 1024} KB)")
    sys.exit(0)
