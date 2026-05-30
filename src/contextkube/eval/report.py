"""Render a scored suite as a human-readable report (markdown).

The per-criterion table is the primary artifact — a CLEAR-style textual insight
into *why* a candidate scored as it did, not just the scalar.
"""

from __future__ import annotations

import os

from contextkube.eval.rubric import SuiteResult

# Branding / disclaimer. Feedback URL is configurable (no hardcoded endpoints).
_FEEDBACK_URL = os.environ.get("AUTONOMYX_FEEDBACK_URL", "https://www.openautonomyx.com/feedback")
_DISCLAIMER = (
    "_AI-generated evaluation by AgentNxt / Autonomyx. "
    "Scores are produced by automated checks and an LLM judge — verify before relying on them. "
    f"Feedback: {_FEEDBACK_URL}_"
)


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def render_markdown(result: SuiteResult) -> str:
    lines: list[str] = []
    lines.append(f"# Eval report — {result.skill_name}\n")
    lines.append(f"**Benchmark score:** {_pct(result.score)}  ")
    lines.append(f"**Deterministic-only (reproducible) score:** {_pct(result.deterministic_score)}\n")

    for case in result.cases:
        lines.append(f"## Eval #{case.case_id} — {_pct(case.score)} "
                     f"(deterministic {_pct(case.deterministic_score)})\n")
        lines.append("| Criterion | Kind | Weight | Score | Detail |")
        lines.append("|---|---|---:|---:|---|")
        for c in case.criteria:
            detail = c.detail.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {c.id} | {c.kind} | {c.weight:g} | {c.pass_score:.2f} | {detail} |")
        lines.append("")

    lines.append("---")
    lines.append(_DISCLAIMER)
    return "\n".join(lines)
