"""The evaluation gate must fail when scores drop, results are stale or a prompt was edited."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from payments_rag import prompts

EVALS = Path(__file__).resolve().parents[1] / "evals"

SUMMARY = {
    "faithfulness_mean": 0.98,
    "correctness_mean_answered": 0.93,
    "correctness_end_to_end": 0.69,
    "correctly_refused": 25,
    "to_refuse": 26,
}
SPEC = {
    "results": "generation.json",
    "require_current_prompts": True,
    "min": {"faithfulness_mean": 0.9, "refused_share": 0.9},
}


@pytest.fixture()
def gate(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.syspath_prepend(str(EVALS))
    import eval_gate

    return eval_gate


def write_results(folder: Path, summary: dict[str, Any], version: str | None) -> None:
    data: dict[str, Any] = {"summary": summary}
    if version is not None:
        data["prompt_version"] = version
    (folder / "generation.json").write_text(json.dumps(data), encoding="utf-8")


def failed(checks: list[Any]) -> list[str]:
    return [c.name for c in checks if not c.passed]


def test_results_that_clear_the_bar_with_current_prompts_pass(gate: Any, tmp_path: Path) -> None:
    write_results(tmp_path, SUMMARY, prompts.prompt_version())

    assert failed(gate.check_generation(SPEC, prompts.prompt_version(), tmp_path)) == []


def test_a_score_below_its_minimum_fails_that_check_only(gate: Any, tmp_path: Path) -> None:
    write_results(tmp_path, {**SUMMARY, "faithfulness_mean": 0.85}, prompts.prompt_version())

    result = gate.check_generation(SPEC, prompts.prompt_version(), tmp_path)

    assert failed(result) == ["generation.json: faithfulness_mean"]


def test_the_refusal_share_is_derived_from_counts(gate: Any) -> None:
    assert gate.derived(SUMMARY)["refused_share"] == pytest.approx(25 / 26)
    assert gate.derived({"to_refuse": 0})["refused_share"] == 0


def test_results_made_with_other_prompts_fail_with_a_hint_to_rerun(
    gate: Any, tmp_path: Path
) -> None:
    write_results(tmp_path, SUMMARY, "000000000000")

    result = gate.check_generation(SPEC, prompts.prompt_version(), tmp_path)

    assert failed(result) == ["generation.json: prompt version"]
    assert "run_generation.py" in result[0].detail


def test_results_without_a_prompt_version_are_treated_as_stale(gate: Any, tmp_path: Path) -> None:
    write_results(tmp_path, SUMMARY, None)

    result = gate.check_generation(SPEC, prompts.prompt_version(), tmp_path)

    assert "generation.json: prompt version" in failed(result)


def test_a_missing_results_file_or_metric_fails(gate: Any, tmp_path: Path) -> None:
    assert failed(gate.check_generation(SPEC, "x", tmp_path)) == ["generation.json: results file"]

    write_results(tmp_path, {"faithfulness_mean": 0.99}, prompts.prompt_version())
    result = gate.check_generation(SPEC, prompts.prompt_version(), tmp_path)

    assert failed(result) == ["generation.json: refused_share"]  # to_refuse missing gives 0


def test_the_prompt_check_can_be_switched_off_for_a_results_file(gate: Any, tmp_path: Path) -> None:
    write_results(tmp_path, SUMMARY, None)

    result = gate.check_generation({**SPEC, "require_current_prompts": False}, "x", tmp_path)

    assert failed(result) == []


def test_the_committed_gate_passes_on_the_committed_tree(gate: Any) -> None:
    checks = gate.run(json.loads((EVALS / "gate.json").read_text(encoding="utf-8")))

    assert failed(checks) == []
    assert len(checks) >= 6  # retrieval and generation checks both ran


def test_editing_a_prompt_makes_the_committed_gate_fail(
    gate: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = prompts.load
    monkeypatch.setattr(
        prompts,
        "load",
        lambda name: original(name) + "\nExtra." if name == "answer" else original(name),
    )
    spec = json.loads((EVALS / "gate.json").read_text(encoding="utf-8"))["generation"][0]

    result = gate.check_generation(spec, prompts.prompt_version(), EVALS)

    assert "generation_no_semantic.json: prompt version" in failed(result)


def test_the_gate_includes_the_guardrail_checks_and_they_pass(gate: Any) -> None:
    checks = gate.run(json.loads((EVALS / "gate.json").read_text(encoding="utf-8")))

    names = [c.name for c in checks]
    assert any(n.startswith("guardrails dev: ") for n in names)
    assert any(n.startswith("guardrails heldout: ") for n in names)
    assert failed(checks) == []


def test_a_weaker_input_guard_would_fail_the_gate(
    gate: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import payments_rag.guardrails.input as guard_input

    monkeypatch.setattr(guard_input, "injection_patterns_match", lambda text: False)

    checks = gate.run({"guardrails": {"dev": {"min": {"attack_block_rate": 0.7}}}})

    assert failed(checks) == ["guardrails dev: attack_block_rate"]


def test_an_input_guard_that_blocks_everything_would_fail_the_false_positive_checks(
    gate: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import payments_rag.guardrails.input as guard_input

    monkeypatch.setattr(guard_input, "injection_patterns_match", lambda text: True)

    checks = gate.run(
        {
            "guardrails": {
                "dev": {"min": {"hard_negative_allowed_rate": 1.0, "golden_allowed_rate": 1.0}}
            }
        }
    )

    assert set(failed(checks)) == {
        "guardrails dev: hard_negative_allowed_rate",
        "guardrails dev: golden_allowed_rate",
    }
