"""Wait until the deployed app reports it is healthy and configured; exit 1 if it never does.

    python capstone/deploy/wait_healthy.py --url https://APP.azurewebsites.net/health [--timeout S]

Run by the deploy job after the app is pointed at a new image. A non-zero exit fails that step,
and GitHub Actions then skips the steps after it, so the registry pruning (which deletes the
previous image) only runs after a healthy deploy.

"Healthy" means /health answers 200 with ``"status": "ok"`` and ``"configured": true``. It does
not say which image answered, so the caller pauses first to let the old instance be replaced.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable


def is_healthy(url: str, timeout: float = 20.0) -> tuple[bool, str]:
    """One probe: (healthy, what was seen). Never raises for network or parsing problems."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (https URL from CI)
            body = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as error:
        return False, f"HTTP {error.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return False, f"no answer ({type(error).__name__})"
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False, f"HTTP {status}, not JSON: {body[:60]!r}"
    ok = status == 200 and data.get("status") == "ok" and data.get("configured") is True
    return ok, body.strip()[:120]


def wait(
    url: str,
    timeout: float,
    interval: float,
    probe: Callable[[str], tuple[bool, str]] = is_healthy,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Probe until healthy or ``timeout`` seconds have passed; always probes at least once."""
    deadline = clock() + timeout
    while True:
        ok, seen = probe(url)
        print(
            f"{time.strftime('%H:%M:%S')} {'healthy' if ok else 'not healthy'}: {seen}", flush=True
        )
        if ok:
            return True
        if clock() >= deadline:
            return False
        sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout", type=float, default=300.0, help="seconds to keep trying")
    parser.add_argument("--interval", type=float, default=10.0)
    args = parser.parse_args(argv)
    if wait(args.url, args.timeout, args.interval):
        return 0
    print(
        f"the app did not report healthy and configured within {args.timeout:.0f} s",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
