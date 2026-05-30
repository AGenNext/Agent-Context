"""Scoring math: weight normalization, judged partial credit, det-only sub-score."""

import pytest

from contextkube.eval.judge import JudgeVerdict
from contextkube.eval.loader import EvalCase
from contextkube.eval.rubric import score_case
from tests.eval.test_checks import BAD_MANIFEST, GOOD_MANIFEST


def _case(rubric):
    return EvalCase(id=99, prompt="p", expected_output="", rubric=rubric)


def stub_judge_pass(*, criterion, prompt, candidate):
    return JudgeVerdict(passed=True, confidence=0.8, rationale="looks good")


def stub_judge_fail(*, criterion, prompt, candidate):
    return JudgeVerdict(passed=False, confidence=0.9, rationale="missing")


def test_all_deterministic_pass_scores_one():
    case = _case([
        {"id": "p", "kind": "deterministic", "check": "parses_as_context_domain", "weight": 1},
        {"id": "f", "kind": "deterministic", "check": "freshness_has_teeth", "weight": 1},
    ])
    r = score_case(case, GOOD_MANIFEST)
    assert r.score == pytest.approx(1.0)
    assert r.deterministic_score == pytest.approx(1.0)


def test_weight_normalization():
    # one passing (weight 3), one failing (weight 1) -> 3/4
    case = _case([
        {"id": "f", "kind": "deterministic", "check": "freshness_has_teeth", "weight": 3},
        {"id": "x", "kind": "deterministic", "check": "tier_monotonicity", "weight": 1},
    ])
    r = score_case(case, BAD_MANIFEST)  # freshness fails here, tier fails here
    # both fail on BAD -> 0
    assert r.score == pytest.approx(0.0)


def test_judged_partial_credit_uses_confidence():
    case = _case([{"id": "j", "kind": "judged", "weight": 1, "criterion": "explains X"}])
    r = score_case(case, "anything", judge=stub_judge_pass)
    assert r.score == pytest.approx(0.8)  # confidence, not 1.0
    assert r.deterministic_score is None   # no deterministic criteria


def test_judged_fail_scores_zero_regardless_of_confidence():
    case = _case([{"id": "j", "kind": "judged", "weight": 1, "criterion": "explains X"}])
    r = score_case(case, "anything", judge=stub_judge_fail)
    assert r.score == pytest.approx(0.0)


def test_mixed_case_combines_det_and_judged():
    case = _case([
        {"id": "f", "kind": "deterministic", "check": "freshness_has_teeth", "weight": 1},
        {"id": "j", "kind": "judged", "weight": 1, "criterion": "explains X"},
    ])
    r = score_case(case, GOOD_MANIFEST, judge=stub_judge_pass)
    # det=1.0 (w1), judged=0.8 (w1) -> 1.8/2 = 0.9
    assert r.score == pytest.approx(0.9)
    assert r.deterministic_score == pytest.approx(1.0)


def test_judged_without_judge_raises():
    case = _case([{"id": "j", "kind": "judged", "weight": 1, "criterion": "explains X"}])
    with pytest.raises(RuntimeError):
        score_case(case, "anything", judge=None)
