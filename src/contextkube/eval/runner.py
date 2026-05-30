"""CLI: score candidate answers against the benchmark and emit a report.

Usage:
    contextkube-eval --suite skills/context-kubernetes/evals/evals.json \
                     --candidates answers.json [--out report.md] [--no-judge]

``--candidates`` is a JSON object mapping eval id (int or str) -> answer text.
With judged criteria present, a GatewayJudge is built from EVAL_JUDGE_* env vars
unless ``--no-judge`` is passed (in which case judged criteria are skipped and
only the deterministic backbone is scored).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contextkube.eval.loader import load_suite
from contextkube.eval.report import render_markdown
from contextkube.eval.rubric import score_suite


def _load_candidates(path: str) -> dict[int, str]:
    raw = json.loads(Path(path).read_text())
    return {int(k): v for k, v in raw.items()}


def _suite_needs_judge(suite) -> bool:
    return any(c.kind == "judged" for case in suite.evals for c in case.rubric)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="contextkube-eval")
    p.add_argument("--suite", required=True, help="path to evals.json")
    p.add_argument("--candidates", required=True, help="JSON: {eval_id: answer_text}")
    p.add_argument("--out", help="write markdown report here (default: stdout)")
    p.add_argument("--no-judge", action="store_true", help="skip judged criteria (deterministic only)")
    args = p.parse_args(argv)

    suite = load_suite(args.suite)
    candidates = _load_candidates(args.candidates)

    judge = None
    if _suite_needs_judge(suite) and not args.no_judge:
        from contextkube.eval.judge import GatewayJudge

        judge = GatewayJudge()

    if args.no_judge:
        # Drop judged criteria so scoring uses only the reproducible backbone.
        for case in suite.evals:
            case.rubric = [c for c in case.rubric if c.kind == "deterministic"]

    result = score_suite(suite, candidates, judge)
    report = render_markdown(result)

    if args.out:
        Path(args.out).write_text(report)
        print(f"wrote {args.out} — benchmark score {result.score * 100:.1f}%")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
