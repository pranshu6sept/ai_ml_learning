"""Build the zip that App Service runs: the `payments_rag` package plus `requirements.txt`.

    (cd capstone/frontend && npm ci && npm run build)      # builds the React page (frontend/dist)
    uv run python capstone/deploy/build_zip.py            # writes capstone/deploy/dist/app.zip
    uv run python capstone/deploy/build_zip.py --api-only # the same without the page

The zip holds the package source, the built React page (as `payments_rag/web/`, which the API
serves at `/`) and the compiled requirements: no `.env`, no tests, no evaluation data, no caches,
no notebooks, no `node_modules`. App Service builds the Python environment from
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
WEB_DIST = HERE.parent / "frontend" / "dist"
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


def build(
    out: Path = OUT,
    source: Path = SOURCE,
    requirements: Path = REQUIREMENTS,
    web: Path | None = WEB_DIST,
) -> list[str]:
    """Write the zip and return the names it contains.

    ``web`` is the built React app; it is required unless ``None`` (an API-only zip), so a deploy
    never silently ships without its page.
    """
    if not requirements.exists():
        raise FileNotFoundError(f"{requirements} is missing; compile it from requirements.in first")
    if web is not None and not (web / "index.html").is_file():
        raise FileNotFoundError(
            f"{web}/index.html is missing; build the page first (cd capstone/frontend && "
            "npm ci && npm run build) or pass --api-only"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(requirements, "requirements.txt")
        names.append("requirements.txt")
        for path in package_files(source):
            name = f"{source.name}/{path.relative_to(source).as_posix()}"
            archive.write(path, name)
            names.append(name)
        if web is not None:
            for path in sorted(p for p in web.rglob("*") if p.is_file()):
                name = f"{source.name}/web/{path.relative_to(web).as_posix()}"
                archive.write(path, name)
                names.append(name)
    return names


if __name__ == "__main__":
    contents = build(web=None if "--api-only" in sys.argv[1:] else WEB_DIST)
    print(f"wrote {OUT} with {len(contents)} files ({OUT.stat().st_size // 1024} KB)")
    sys.exit(0)
