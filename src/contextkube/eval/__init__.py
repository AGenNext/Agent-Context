"""Eval harness for the context-kubernetes skill.

A *hybrid* metric: deterministic invariant checks (reusing the permission
engine) for machine-verifiable criteria, plus an LLM judge for the
reasoning/pushback criteria a parser cannot score. See
``docs/superpowers/specs/2026-05-30-agentkube-eval-metric-benchmark-design.md``.
"""

from contextkube.eval.loader import Criterion, EvalCase, EvalSuite, load_suite
from contextkube.eval.rubric import CaseResult, CriterionResult, SuiteResult, score_case, score_suite

__all__ = [
    "Criterion",
    "EvalCase",
    "EvalSuite",
    "load_suite",
    "CaseResult",
    "CriterionResult",
    "SuiteResult",
    "score_case",
    "score_suite",
]
