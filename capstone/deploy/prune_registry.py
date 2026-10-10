"""Keep exactly one image in the container registry: the one that was just deployed.

    python capstone/deploy/prune_registry.py --registry NAME --keep TAG [--repository R] [--dry-run]

Run by the deploy job after the new image is live and healthy. It lists every manifest in the
repository (tagged or not) and deletes all except the one carrying ``--keep``. It refuses to
delete anything when the kept tag is not found, so a typo or an earlier failed push cannot empty
the registry.

The signed-in identity needs the ``AcrDelete`` role on the registry (see infra/week8.bicep). Uses
only the standard library and the Azure CLI.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from typing import Any


class KeepNotFoundError(Exception):
    """The image to keep is not in the repository; deleting the rest would remove every image."""


def stale_digests(manifests: list[dict[str, Any]], keep_tag: str) -> list[str]:
    """Digests of every manifest that does not carry ``keep_tag``; raises if none does."""
    if not any(keep_tag in (m.get("tags") or []) for m in manifests):
        raise KeepNotFoundError(f"no image tagged {keep_tag!r}; refusing to delete anything")
    return [m["digest"] for m in manifests if keep_tag not in (m.get("tags") or [])]


def az(*args: str) -> str:
    # shutil.which finds `az.cmd` on Windows, where a bare "az" cannot be launched.
    executable = shutil.which("az") or "az"
    result = subprocess.run([executable, *args], capture_output=True, text=True, check=True)
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--registry", required=True)
    parser.add_argument("--keep", required=True, help="the tag of the image to keep")
    parser.add_argument("--repository", default="payrag-api")
    parser.add_argument("--dry-run", action="store_true", help="list what would be deleted")
    args = parser.parse_args(argv)

    manifests = json.loads(
        az(
            "acr",
            "manifest",
            "list-metadata",
            "-r",
            args.registry,
            "-n",
            args.repository,
            "-o",
            "json",
        )
    )
    try:
        stale = stale_digests(manifests, args.keep)
    except KeepNotFoundError as error:
        print(error, file=sys.stderr)
        return 1
    for digest in stale:
        print(f"{'would delete' if args.dry_run else 'deleting'} {args.repository}@{digest}")
        if not args.dry_run:
            az(
                "acr",
                "repository",
                "delete",
                "--name",
                args.registry,
                "--image",
                f"{args.repository}@{digest}",
                "--yes",
            )
    verb = "listed" if args.dry_run else "deleted"
    print(f"kept {args.repository}:{args.keep}; {len(stale)} other image(s) {verb}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
