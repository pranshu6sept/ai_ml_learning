"""The HTTP layer, tested with a fake answerer (no Azure, no network)."""

import logging
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from payments_rag.api import MAX_QUESTION_CHARS, RateLimiter, create_app  # noqa: E402
from payments_rag.ask import Answer  # noqa: E402


def _answer(question: str) -> Answer:
    return Answer(
        question, "ISO 20022 is a standard [1].", ("[1] iso > S (http://x)",), False, "ok"
    )


class Counter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, question: str) -> Answer:
        self.calls.append(question)
        return _answer(question)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _client(answerer=_answer, **options) -> TestClient:  # type: ignore[no-untyped-def]
    return TestClient(create_app(answerer, configured=lambda: True, **options))


def test_health_needs_no_azure_and_reports_whether_settings_are_present() -> None:
    assert _client().get("/health").json() == {"status": "ok", "configured": True}
    unconfigured = TestClient(create_app(_answer, configured=lambda: False))

    assert unconfigured.get("/health").json() == {"status": "ok", "configured": False}


def test_a_question_gets_a_cited_answer_with_a_request_id_and_latency() -> None:
    response = _client().post("/ask", json={"question": "What is ISO 20022?"})

    body = response.json()
    assert response.status_code == 200
    assert body["answer"] == "ISO 20022 is a standard [1]."
    assert body["sources"] == ["[1] iso > S (http://x)"] and body["refused"] is False
    assert len(body["request_id"]) == 32 and body["latency_ms"] >= 0


def test_a_refusal_is_a_normal_200_with_the_reason() -> None:
    def refuse(question: str) -> Answer:
        return Answer(question, "I don't know based on the provided documents.", (), True, "none")

    body = _client(refuse).post("/ask", json={"question": "Who won?"}).json()

    assert body["refused"] is True and body["sources"] == [] and body["reason"] == "none"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"question": ""},
        {"question": "x" * (MAX_QUESTION_CHARS + 1)},
        {"question": 5},
        {"question": "ok", "extra": 1},
    ],
)
def test_bad_requests_are_rejected_before_any_model_call(payload: dict[str, object]) -> None:
    counter = Counter()

    response = _client(counter).post("/ask", json=payload)

    assert response.status_code == 422
    assert counter.calls == []


def test_the_longest_allowed_question_goes_through() -> None:
    counter = Counter()

    response = _client(counter).post("/ask", json={"question": "x" * MAX_QUESTION_CHARS})

    assert response.status_code == 200 and len(counter.calls) == 1


def test_the_rate_limit_rejects_the_call_after_the_limit_with_retry_after() -> None:
    counter, clock = Counter(), Clock()
    client = _client(counter, rate_per_minute=2, clock=clock)

    codes = [client.post("/ask", json={"question": "q"}).status_code for _ in range(3)]
    limited = client.post("/ask", json={"question": "q"})

    assert codes == [200, 200, 429]
    assert int(limited.headers["retry-after"]) >= 1
    assert len(counter.calls) == 2  # rejected calls never reach the model
    clock.now += 61
    assert client.post("/ask", json={"question": "q"}).status_code == 200  # the window moved on


def test_invalid_requests_do_not_use_up_the_rate_limit() -> None:
    client = _client(rate_per_minute=1)

    client.post("/ask", json={"question": ""})

    assert client.post("/ask", json={"question": "q"}).status_code == 200


def test_the_rate_limiter_counts_a_rolling_minute() -> None:
    clock = Clock()
    limiter = RateLimiter(2, clock)

    assert limiter.allow() and limiter.allow() and not limiter.allow()
    clock.now += 30
    assert not limiter.allow()
    clock.now += 31  # the first two calls are now over a minute old
    assert limiter.allow()


def test_an_api_key_is_required_when_one_is_configured() -> None:
    counter = Counter()
    client = _client(counter, api_key="s3cret")

    assert client.post("/ask", json={"question": "q"}).status_code == 401
    assert (
        client.post("/ask", json={"question": "q"}, headers={"X-API-Key": "wrong"}).status_code
        == 401
    )
    assert (
        client.post("/ask", json={"question": "q"}, headers={"X-API-Key": "s3cret"}).status_code
        == 200
    )
    assert len(counter.calls) == 1
    assert client.get("/health").status_code == 200  # health stays open for probes


def test_a_missing_key_is_reported_before_a_bad_body() -> None:
    response = _client(api_key="s3cret").post("/ask", json={"question": ""})

    assert response.status_code == 401  # not 422: do not reveal validation details to strangers


def test_an_api_key_can_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAYRAG_API_KEY", "from-env")
    client = TestClient(create_app(_answer, configured=lambda: True))

    assert client.post("/ask", json={"question": "q"}).status_code == 401
    assert (
        client.post("/ask", json={"question": "q"}, headers={"X-API-Key": "from-env"}).status_code
        == 200
    )


def test_a_failure_inside_the_pipeline_is_a_502_that_does_not_leak_the_cause(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(question: str) -> Answer:
        raise RuntimeError("secret-endpoint.example.com refused the connection")

    with caplog.at_level(logging.ERROR, logger="payments_rag.api"):
        response = _client(broken).post("/ask", json={"question": "q"})

    assert response.status_code == 502
    assert "secret-endpoint" not in response.text
    assert "secret-endpoint" in caplog.text  # the cause is in the log for the operator


def test_the_default_pipeline_is_not_built_until_the_first_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[int] = []

    def fake_default() -> object:
        built.append(1)
        return _answer

    monkeypatch.setattr("payments_rag.api.default_answerer", fake_default)
    client = TestClient(create_app(None, configured=lambda: True))

    assert client.get("/health").status_code == 200 and built == []
    client.post("/ask", json={"question": "q"})
    client.post("/ask", json={"question": "q"})
    assert built == [1]  # built once, then reused


def test_feedback_is_stored_and_validated() -> None:
    app = create_app(_answer, configured=lambda: True)
    client = TestClient(app)

    ok = client.post("/feedback", json={"request_id": "abc", "rating": "up", "comment": "good"})
    bad = client.post("/feedback", json={"request_id": "abc", "rating": "meh"})

    assert ok.json() == {"stored": True} and bad.status_code == 422
    assert list(app.state.feedback.items) == [
        {"request_id": "abc", "rating": "up", "comment": "good"}
    ]


def _web(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(
        "<!doctype html><title>Payments Assistant</title>", encoding="utf-8"
    )
    (root / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return root


def _web_client(tmp_path: Path, **options) -> TestClient:  # type: ignore[no-untyped-def]
    app = create_app(_answer, configured=lambda: True, web_root=_web(tmp_path), **options)
    return TestClient(app)


def test_the_built_page_is_served_at_the_root_and_its_files_under_assets(tmp_path: Path) -> None:
    client = _web_client(tmp_path)

    page = client.get("/")

    assert page.status_code == 200 and "Payments Assistant" in page.text
    assert client.get("/assets/app.js").text == "console.log(1)"


def test_the_page_does_not_shadow_the_api_or_the_docs(tmp_path: Path) -> None:
    client = _web_client(tmp_path, api_key="k")

    assert client.get("/health").json()["status"] == "ok"
    assert client.post("/ask", json={"question": "q"}).status_code == 401  # still protected
    assert (
        client.post("/ask", json={"question": "q"}, headers={"X-API-Key": "k"}).status_code == 200
    )
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_the_api_key_never_protects_the_page_itself_but_the_page_holds_no_key(
    tmp_path: Path,
) -> None:
    client = _web_client(tmp_path, api_key="topsecret")

    assert client.get("/").status_code == 200
    assert "topsecret" not in client.get("/").text


def test_responses_carry_security_headers_and_a_strict_csp(tmp_path: Path) -> None:
    client = _web_client(tmp_path)

    for path in ("/", "/health", "/assets/app.js"):
        headers = client.get(path).headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["referrer-policy"] == "no-referrer"
        csp = headers["content-security-policy"]
        assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp


def test_the_docs_page_keeps_working_because_it_is_left_out_of_the_csp(tmp_path: Path) -> None:
    headers = _web_client(tmp_path).get("/docs").headers

    assert "content-security-policy" not in headers
    assert headers["x-content-type-options"] == "nosniff"


def test_an_unknown_path_is_a_404_not_the_page(tmp_path: Path) -> None:
    assert _web_client(tmp_path).get("/nope").status_code == 404


def test_without_a_built_page_the_root_is_a_404_and_the_api_still_works(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PAYRAG_WEB_DIR", str(tmp_path / "nothing-here"))
    client = TestClient(create_app(_answer, configured=lambda: True))

    assert client.get("/").status_code == 404
    assert client.post("/ask", json={"question": "q"}).status_code == 200


def test_serve_web_false_turns_the_page_off(tmp_path: Path) -> None:
    app = create_app(_answer, configured=lambda: True, serve_web=False, web_root=_web(tmp_path))

    assert TestClient(app).get("/").status_code == 404


def test_the_page_location_can_come_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PAYRAG_WEB_DIR", str(_web(tmp_path)))

    assert TestClient(create_app(_answer, configured=lambda: True)).get("/").status_code == 200
