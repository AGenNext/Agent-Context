"""Scoring: combine deterministic + judged criteria into a [0, 1] eval score.

Per-criterion pass score:
  * deterministic  -> 1.0 if the check passes, else 0.0   (crisp, reproducible)
  * judged         -> judge.confidence if passed, else 0.0 (confidence = partial credit)

A criterion's contribution is ``weight * pass_score``; the eval score is the
weight-normalized sum, so it always lands in [0, 1] regardless of raw weights.
The suite score is the unweighted mean of eval scores.

We also surface a *deterministic-only* sub-score: the same computation over just
the deterministic criteria. That sub-score is model-independent and reproducible
— the stable backbone of the leaderboard.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from contextkube.eval.checks import run_check
from contextkube.eval.judge import Judge, JudgeVerdict
from contextkube.eval.loader import EvalCase, EvalSuite


class CriterionResult(BaseModel):
    id: str
    kind: str
    weight: float
    pass_score: float = Field(ge=0.0, le=1.0)
    detail: str


class CaseResult(BaseModel):
    case_id: int
    score: float
    deterministic_score: float | None  # None if the case has no deterministic criteria
    criteria: list[CriterionResult]


class SuiteResult(BaseModel):
    skill_name: str
    score: float
    deterministic_score: float | None
    cases: list[CaseResult]


def _normalize(results: list[CriterionResult]) -> float | None:
    total_weight = sum(r.weight for r in results)
    if total_weight == 0:
        return None
    return sum(r.weight * r.pass_score for r in results) / total_weight


def score_case(case: EvalCase, candidate: str, judge: Judge | None = None) -> CaseResult:
    """Score one candidate answer against an eval's rubric."""
    results: list[CriterionResult] = []
    for c in case.rubric:
        if c.kind == "deterministic":
            cr = run_check(c.check, candidate)  # type: ignore[arg-type]
            results.append(
                CriterionResult(
                    id=c.id, kind=c.kind, weight=c.weight,
                    pass_score=1.0 if cr.passed else 0.0, detail=cr.detail,
                )
            )
        else:  # judged
            if judge is None:
                raise RuntimeError(
                    f"case {case.id} has judged criterion {c.id!r} but no judge was supplied"
                )
            v: JudgeVerdict = judge(criterion=c.criterion or "", prompt=case.prompt, candidate=candidate)
            results.append(
                CriterionResult(
                    id=c.id, kind=c.kind, weight=c.weight,
                    pass_score=v.confidence if v.passed else 0.0,
                    detail=f"[conf {v.confidence:.2f}] {v.rationale}",
                )
            )

    det = [r for r in results if r.kind == "deterministic"]
    return CaseResult(
        case_id=case.id,
        score=_normalize(results) or 0.0,
        deterministic_score=_normalize(det),
        criteria=results,
    )


def score_suite(suite: EvalSuite, candidates: dict[int, str], judge: Judge | None = None) -> SuiteResult:
    """Score a whole suite. ``candidates`` maps eval id -> candidate answer text."""
    cases = [
        score_case(case, candidates.get(case.id, ""), judge)
        for case in suite.evals
        if case.rubric  # only scorable evals contribute
    ]
    overall = sum(c.score for c in cases) / len(cases) if cases else 0.0
    det_scores = [c.deterministic_score for c in cases if c.deterministic_score is not None]
    det_overall = sum(det_scores) / len(det_scores) if det_scores else None
    return SuiteResult(
        skill_name=suite.skill_name,
        score=overall,
        deterministic_score=det_overall,
        cases=cases,
    )
