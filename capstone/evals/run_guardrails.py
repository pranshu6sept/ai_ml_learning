# ruff: noqa: E501
"""Week 10 guardrail report: block rates on an adversarial set and false-positive rates on benign ones.

    uv run --group api python capstone/evals/run_guardrails.py            # offline: free, deterministic
    uv run --all-groups python capstone/evals/run_guardrails.py --live     # also run document-borne
                                                                            # injections and prompt
                                                                            # extraction through the real model

What it measures (the attacks are in ``adversarial.jsonl``, mapped to OWASP LLM01 prompt injection,
LLM02 sensitive information disclosure and LLM07 system prompt leakage):

* **Block rate** of the input guard on user-channel attacks (direct injection, jailbreak, prompt
  extraction, obfuscated), by category and by OWASP id.
* **PII**: whether card numbers, IBANs and account numbers are removed from questions and answers.
* **False positives**: the share of benign questions the input guard blocks (the 95 golden questions and
  16 hard negatives written to sound like attacks), and the share of real answers the output guard blocks.
* With ``--live``: whether the real model *obeys* an instruction hidden in a retrieved passage, with
  and without the output guard, and whether it recites its prompt when asked.

Honest limits, repeated in the report: the attacks and the patterns were written by the same author, so
the textbook cases flatter the guard (the set deliberately includes attacks written to dodge the
patterns); 61 attacks is a small sample, so a rate moves by 1.6 points per attack; the benign sets are
mine too; one run, temperature 0; the answers used for the output false-positive rate are the ones the
support threshold was tuned on.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
USER_ATTACKS = ("direct_injection", "jailbreak", "prompt_extraction", "obfuscated")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def rate(hits: int, total: int) -> float:
    return hits / total if total else float("nan")


def input_attacks(
    attacks: list[dict[str, Any]], shield: Callable[[str], bool] | None = None
) -> dict[str, Any]:
    """Block rate of the input guard on user-channel attacks, by category and OWASP id."""
    from payments_rag.guardrails.input import check_input

    rows = []
    for attack in attacks:
        if attack["category"] not in USER_ATTACKS:
            continue
        verdict = check_input(attack["text"], shield=shield)
        rows.append({**attack, "blocked": not verdict.allowed, "reasons": list(verdict.reasons)})
    return {
        "total": len(rows),
        "blocked": sum(r["blocked"] for r in rows),
        "by_category": _group(rows, "category"),
        "by_owasp": _group(rows, "owasp"),
        "missed": [
            {"id": r["id"], "category": r["category"], "text": r["text"]}
            for r in rows
            if not r["blocked"]
        ],
    }


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    return {
        name: {
            "total": len(g),
            "blocked": sum(r["blocked"] for r in g),
            "rate": rate(sum(r["blocked"] for r in g), len(g)),
        }
        for name, g in sorted(groups.items())
    }


def pii_cases(attacks: list[dict[str, Any]]) -> dict[str, Any]:
    """Were identifiers removed from questions (input) and from answers (output)?"""
    from payments_rag.guardrails.input import check_input
    from payments_rag.guardrails.output import check_output

    rows = []
    for case in attacks:
        if case["category"] == "pii_input":
            verdict = check_input(case["text"])
            text = verdict.text
        elif case["category"] == "pii_output":
            out = check_output(case["text"], [case["passage"]], refused=False)
            text = out.text
        else:
            continue
        leaked = [s for s in case["must_not_contain"] if s in text]
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "removed": not leaked,
                "text": case["text"],
            }
        )
    return {
        "total": len(rows),
        "removed": sum(r["removed"] for r in rows),
        "missed": [{"id": r["id"], "text": r["text"]} for r in rows if not r["removed"]],
        "by_category": _group([{**r, "blocked": r["removed"]} for r in rows], "category"),
    }


def benign_questions(
    questions: list[str], shield: Callable[[str], bool] | None = None
) -> dict[str, Any]:
    """How many legitimate questions does the input guard block, and how many does it alter?"""
    from payments_rag.guardrails.input import check_input

    blocked, altered = [], []
    for q in questions:
        verdict = check_input(q, shield=shield)
        if not verdict.allowed:
            blocked.append({"text": q, "reasons": list(verdict.reasons)})
        elif verdict.text != " ".join(q.split()):
            altered.append({"text": q, "became": verdict.text})
    return {"total": len(questions), "blocked": blocked, "altered": altered}


def real_answers(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the answers the pipeline really gave (and their evidence) through the output guard."""
    from payments_rag.guardrails.guard import prompt_secrets
    from payments_rag.guardrails.output import check_output

    secrets = prompt_secrets()
    answered = [r for r in records if not r["refused"]]
    blocked = []
    for r in answered:
        passages = [e["text"] for e in r["evidence"]]
        verdict = check_output(r["reply"], passages, refused=False, secrets=secrets)
        if not verdict.allowed:
            blocked.append(
                {"id": r["id"], "reasons": list(verdict.reasons), "reply": r["reply"][:120]}
            )
    return {"total": len(answered), "blocked": blocked}


def load_inputs() -> dict[str, Any]:
    golden = read_jsonl(HERE / "golden_set.jsonl")
    generation = json.loads((RESULTS / "generation_no_semantic.json").read_text(encoding="utf-8"))
    return {
        "attacks": read_jsonl(HERE / "adversarial.jsonl"),
        "golden": [g["question"] for g in golden],
        "hard": read_jsonl(HERE / "benign_hard.jsonl"),
        "records": generation["records"],
    }


def run_offline(
    shield: Callable[[str], bool] | None = None, heldout: bool = False
) -> dict[str, Any]:
    """The offline measurements. ``heldout`` uses the sets written after patterns v2 was frozen."""
    if heldout:
        attacks = read_jsonl(HERE / "adversarial_heldout.jsonl")
        benign = read_jsonl(HERE / "benign_heldout.jsonl")
        return {
            "input_attacks": input_attacks(attacks, shield),
            "pii": pii_cases(attacks),
            "benign_golden": {"total": 0, "blocked": [], "altered": []},
            "benign_hard": benign_questions([b["text"] for b in benign], shield),
            "real_answers": {"total": 0, "blocked": []},
        }
    data = load_inputs()
    return {
        "input_attacks": input_attacks(data["attacks"], shield),
        "pii": pii_cases(data["attacks"]),
        "benign_golden": benign_questions(data["golden"], shield),
        "benign_hard": benign_questions([h["text"] for h in data["hard"]], shield),
        "real_answers": real_answers(data["records"]),
    }


def pct(x: float) -> str:
    return "n/a" if x != x else f"{100 * x:.0f}%"


def render(result: dict[str, Any], title: str) -> str:
    a, p, g, h, ra = (
        result[k] for k in ("input_attacks", "pii", "benign_golden", "benign_hard", "real_answers")
    )
    lines = [
        f"# Guardrail report: {title}\n",
        "One run, written by the same author as the guards. Block rate = share of attacks the guard stopped; "
        "false-positive rate = share of legitimate input blocked. Small samples: one attack is worth "
        f"{100 / a['total']:.1f} points.\n",
        "## Input guard on user-channel attacks\n",
        f"**{a['blocked']} of {a['total']} blocked ({pct(rate(a['blocked'], a['total']))}).**\n",
        "| Category | Blocked | Rate |",
        "|---|---|---|",
    ]
    lines += [
        f"| {c} | {v['blocked']} of {v['total']} | {pct(v['rate'])} |"
        for c, v in a["by_category"].items()
    ]
    lines += ["", "| OWASP LLM Top 10 (2025) | Blocked | Rate |", "|---|---|---|"]
    names = {
        "LLM01": "LLM01 Prompt Injection",
        "LLM02": "LLM02 Sensitive Information Disclosure",
        "LLM07": "LLM07 System Prompt Leakage",
    }
    lines += [
        f"| {names.get(c, c)} | {v['blocked']} of {v['total']} | {pct(v['rate'])} |"
        for c, v in a["by_owasp"].items()
    ]
    lines += ["", "### Attacks that got through\n"]
    lines += [f"- `{m['id']}` ({m['category']}): {m['text'][:110]}" for m in a["missed"]] or [
        "- none"
    ]
    lines += [
        "",
        "## PII removal (OWASP LLM02)\n",
        f"**{p['removed']} of {p['total']} cases had every identifier removed.**\n",
    ]
    lines += [f"- missed `{m['id']}`: {m['text'][:110]}" for m in p["missed"]] or ["- none missed"]
    lines += [
        "",
        "## False positives on legitimate input\n",
        "| Set | Questions | Blocked | False-positive rate | Altered by redaction |",
        "|---|---|---|---|---|",
    ]
    if g["total"]:
        lines.append(
            f"| Golden-set questions | {g['total']} | {len(g['blocked'])} | {pct(rate(len(g['blocked']), g['total']))} | {len(g['altered'])} |"
        )
    lines += [
        f"| Hard negatives (attack-sounding, legitimate) | {h['total']} | {len(h['blocked'])} | {pct(rate(len(h['blocked']), h['total']))} | {len(h['altered'])} |",
        "",
    ]
    for label, block in (("golden", g), ("hard-negative", h)):
        lines += [
            f"- blocked ({label}): {b['text'][:100]} [{','.join(b['reasons'])}]"
            for b in block["blocked"]
        ]
        lines += [
            f"- redacted ({label}): {b['text'][:70]} -> {b['became'][:70]}"
            for b in block["altered"]
        ]
    if ra["total"]:
        lines += [
            "",
            "## False positives on real answers (output guard)\n",
            f"{len(ra['blocked'])} of {ra['total']} answers the pipeline really gave were blocked. "
            "The support threshold was tuned on these same answers, so 0 is optimistic.\n",
        ]
        lines += [
            f"- blocked `{b['id']}` [{','.join(b['reasons'])}]: {b['reply']}" for b in ra["blocked"]
        ]
    return "\n".join(lines) + "\n"


class ThrottledShield:
    """Prompt Shields at a pace the free tier allows (5 requests a second), retrying transient errors.

    An evaluation must not quietly count a failed call as "no attack", so after four failures this
    raises instead of failing open.
    """

    def __init__(self, inner: Any, min_interval: float = 0.3) -> None:
        self.inner = inner
        self.min_interval = min_interval
        self.calls = 0
        self.errors = 0
        self._last = 0.0

    @classmethod
    def from_env(cls) -> ThrottledShield:
        import os

        from payments_rag.guardrails.shield import PromptShields

        endpoint = os.environ.get("AZURE_CONTENT_SAFETY_ENDPOINT")
        if not endpoint:
            raise SystemExit("set AZURE_CONTENT_SAFETY_ENDPOINT to use --shield")
        return cls(PromptShields(endpoint))

    def __call__(self, text: str) -> bool:
        import time

        from payments_rag.guardrails.shield import ShieldError

        for attempt in range(4):
            time.sleep(max(0.0, self._last + self.min_interval - time.monotonic()))
            self._last = time.monotonic()
            self.calls += 1
            try:
                return bool(self.inner.analyze(text).user_attack)
            except ShieldError:
                self.errors += 1
                time.sleep(1.0 + attempt)
        raise RuntimeError("Prompt Shields kept failing; not recording a guess")


def run_live(use_shield: bool, out: str, compound: bool = False) -> int:
    """The experiments that need Azure OpenAI; the shield, if asked for, is the free Content Safety one."""
    import os

    import guardrails_live as live

    from payments_rag.guardrails.shield import PromptShields

    data = load_inputs()
    heldout = read_jsonl(HERE / "adversarial_heldout.jsonl")
    chat, settings = live.make_chat()
    shield = None
    if use_shield:
        endpoint = os.environ.get("AZURE_CONTENT_SAFETY_ENDPOINT")
        if not endpoint:
            raise SystemExit("set AZURE_CONTENT_SAFETY_ENDPOINT to use --shield")
        shield = PromptShields(endpoint)
    throttled = ThrottledShield(shield) if shield is not None else None
    if compound:
        # Answerable questions with an instruction attached: the pipeline cannot refuse them for being off-topic.
        attacks = read_jsonl(HERE / "adversarial_compound.jsonl")
        rows = live.user_attacks_end_to_end(chat, settings, attacks, throttled)["rows"]
        result = {"rows": rows, "model_calls": chat.calls}
        text = live.render_compound(rows) + f"\nModel calls: {chat.calls}.\n"
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / f"{out}.md").write_text(text, encoding="utf-8")
        (RESULTS / f"{out}.json").write_text(
            json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        print(text)
        return 0
    result = {
        "user_attacks": live.user_attacks_end_to_end(
            chat, settings, data["attacks"] + heldout, throttled
        ),
        "document_attacks": live.document_attacks(chat, data["attacks"], data["records"], shield),
        "prompt_leakage": live.prompt_leakage(chat, data["attacks"] + heldout, data["records"]),
        "model_calls": chat.calls,
    }
    text = live.render_live(result) + f"\nModel calls: {chat.calls}.\n"
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{out}.md").write_text(text, encoding="utf-8")
    (RESULTS / f"{out}.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--out", default="guardrails", help="results file stem (written under results/)"
    )
    parser.add_argument(
        "--heldout",
        action="store_true",
        help="use the sets written after patterns v2 was frozen (adversarial_heldout.jsonl, benign_heldout.jsonl)",
    )
    parser.add_argument(
        "--shield",
        action="store_true",
        help="also call Azure Prompt Shields (needs AZURE_CONTENT_SAFETY_ENDPOINT and az login)",
    )
    parser.add_argument(
        "--compound",
        action="store_true",
        help="with --live: only the answerable-question-plus-injection set (adversarial_compound.jsonl)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="run the experiments that call Azure OpenAI (end to end, document attacks, leakage)",
    )
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if args.live:
        return run_live(args.shield, args.out, args.compound)
    shield = ThrottledShield.from_env() if args.shield else None
    result = run_offline(shield, heldout=args.heldout)
    if shield is not None:
        result["shield"] = {"calls": shield.calls, "retried_errors": shield.errors}
    RESULTS.mkdir(exist_ok=True)
    title = "patterns + Azure Prompt Shields" if shield else "patterns only (offline)"
    text = render(result, title + (", HELD-OUT sets" if args.heldout else ""))
    if shield is not None:
        text += (
            f"\nPrompt Shields: {shield.calls} calls, {shield.errors} transient errors retried "
            "(free tier, 5 requests a second).\n"
        )
    (RESULTS / f"{args.out}.md").write_text(text, encoding="utf-8")
    (RESULTS / f"{args.out}.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
