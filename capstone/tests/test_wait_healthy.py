# ruff: noqa: E501
"""The deploy job's health gate: it must fail (exit 1) unless the app is healthy AND configured."""

from __future__ import annotations

import importlib.util
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "wait_healthy.py"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("wait_healthy", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def server() -> Iterator[Any]:
    """A real local HTTP server whose /health reply the test chooses."""
    reply: dict[str, Any] = {"code": 200, "body": json.dumps({"status": "ok", "configured": True})}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (http.server requires this name)
            payload = reply["body"].encode()
            self.send_response(reply["code"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args: Any) -> None:
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    reply["url"] = f"http://127.0.0.1:{httpd.server_port}/health"
    yield reply
    httpd.shutdown()


def test_healthy_and_configured_passes(server: dict[str, Any]) -> None:
    assert load().is_healthy(server["url"])[0] is True
    assert load().main(["--url", server["url"], "--timeout", "1", "--interval", "0.1"]) == 0


def test_up_but_not_configured_fails(server: dict[str, Any]) -> None:
    server["body"] = json.dumps({"status": "ok", "configured": False})

    assert load().is_healthy(server["url"])[0] is False
    assert load().main(["--url", server["url"], "--timeout", "0.3", "--interval", "0.1"]) == 1


def test_a_server_error_fails(server: dict[str, Any]) -> None:
    server["code"] = 503
    server["body"] = "Service Unavailable"

    ok, seen = load().is_healthy(server["url"])

    assert (ok, seen) == (False, "HTTP 503")
    assert load().main(["--url", server["url"], "--timeout", "0.3", "--interval", "0.1"]) == 1


def test_a_page_that_is_not_json_fails(server: dict[str, Any]) -> None:
    server["body"] = "<html>Application Error</html>"

    ok, seen = load().is_healthy(server["url"])

    assert ok is False and "not JSON" in seen


def test_nothing_listening_fails_without_raising() -> None:
    ok, seen = load().is_healthy("http://127.0.0.1:9/health", timeout=1.0)

    assert ok is False and seen.startswith("no answer")


def test_it_keeps_trying_until_the_app_comes_up() -> None:
    module = load()
    answers = iter([(False, "HTTP 503"), (False, "HTTP 503"), (True, "ok")])
    slept: list[float] = []

    result = module.wait(
        "u",
        timeout=60,
        interval=10,
        probe=lambda u: next(answers),
        sleep=slept.append,
        clock=lambda: 0.0,
    )

    assert result is True and slept == [10, 10]


def test_it_gives_up_at_the_timeout_and_probes_at_least_once() -> None:
    module = load()
    now = [0.0]
    probes: list[str] = []

    def probe(url: str) -> tuple[bool, str]:
        probes.append(url)
        return False, "HTTP 503"

    def sleep(seconds: float) -> None:
        now[0] += seconds

    result = module.wait(
        "u", timeout=25, interval=10, probe=probe, sleep=sleep, clock=lambda: now[0]
    )

    assert result is False
    assert (
        len(probes) == 4
    )  # at 0, 10, 20 and 30 s: the last probe is the first one past the deadline
    assert (
        module.wait("u", timeout=0, interval=1, probe=probe, sleep=sleep, clock=lambda: now[0])
        is False
    )
