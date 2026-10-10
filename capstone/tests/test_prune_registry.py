"""The registry pruning keeps exactly the deployed image and never empties the registry."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "prune_registry.py"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("prune_registry", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MANIFESTS = [
    {"digest": "sha256:keep", "tags": ["abc123"]},
    {"digest": "sha256:old", "tags": ["def456"]},
    {"digest": "sha256:untagged", "tags": None},
    {"digest": "sha256:two", "tags": ["x", "y"]},
]


def test_everything_except_the_kept_image_is_stale() -> None:
    assert load().stale_digests(MANIFESTS, "abc123") == [
        "sha256:old",
        "sha256:untagged",
        "sha256:two",
    ]


def test_an_image_with_several_tags_is_kept_if_any_tag_matches() -> None:
    assert "sha256:two" not in load().stale_digests(MANIFESTS, "y")


def test_the_tag_must_match_exactly_not_by_prefix() -> None:
    module = load()

    with pytest.raises(module.KeepNotFoundError):
        module.stale_digests(MANIFESTS, "abc")


def test_nothing_is_deleted_when_the_kept_tag_is_missing() -> None:
    module = load()

    with pytest.raises(module.KeepNotFoundError):
        module.stale_digests(MANIFESTS, "no-such-tag")
    with pytest.raises(module.KeepNotFoundError):
        module.stale_digests([], "abc123")


def test_a_registry_with_only_the_kept_image_has_nothing_to_delete() -> None:
    assert load().stale_digests([MANIFESTS[0]], "abc123") == []


def test_main_deletes_only_stale_digests(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    module = load()
    calls: list[tuple[str, ...]] = []

    def fake_az(*args: str) -> str:
        calls.append(args)
        return json.dumps(MANIFESTS) if args[:3] == ("acr", "manifest", "list-metadata") else ""

    monkeypatch.setattr(module, "az", fake_az)

    code = module.main(["--registry", "reg", "--keep", "abc123"])

    deletes = [c for c in calls if c[:3] == ("acr", "repository", "delete")]
    assert code == 0
    assert [c[c.index("--image") + 1] for c in deletes] == [
        "payrag-api@sha256:old",
        "payrag-api@sha256:untagged",
        "payrag-api@sha256:two",
    ]
    assert "kept payrag-api:abc123; 3 other" in capsys.readouterr().out


def test_main_refuses_and_deletes_nothing_when_the_kept_tag_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load()
    calls: list[tuple[str, ...]] = []

    def fake_az(*args: str) -> str:
        calls.append(args)
        return json.dumps(MANIFESTS)

    monkeypatch.setattr(module, "az", fake_az)

    code = module.main(["--registry", "reg", "--keep", "missing"])

    assert code == 1
    assert not [c for c in calls if c[:3] == ("acr", "repository", "delete")]


def test_dry_run_deletes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load()
    calls: list[tuple[str, ...]] = []

    def fake_az(*args: str) -> str:
        calls.append(args)
        return json.dumps(MANIFESTS)

    monkeypatch.setattr(module, "az", fake_az)

    assert module.main(["--registry", "reg", "--keep", "abc123", "--dry-run"]) == 0
    assert not [c for c in calls if c[:3] == ("acr", "repository", "delete")]
