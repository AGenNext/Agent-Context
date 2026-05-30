"""Loader validates the real evals.json and enforces criterion shape."""

import pytest
from pydantic import ValidationError

from contextkube.eval.loader import Criterion, load_suite

EVALS = "skills/context-kubernetes/evals/evals.json"


def test_loads_real_suite():
    suite = load_suite(EVALS)
    assert suite.skill_name == "context-kubernetes"
    assert len(suite.evals) == 3
    assert all(case.rubric for case in suite.evals)  # every eval now scorable


def test_case_lookup():
    suite = load_suite(EVALS)
    assert suite.case(1).id == 1
    with pytest.raises(KeyError):
        suite.case(404)


def test_deterministic_criterion_requires_check():
    with pytest.raises(ValidationError):
        Criterion(id="x", kind="deterministic", weight=1)


def test_judged_criterion_requires_text():
    with pytest.raises(ValidationError):
        Criterion(id="x", kind="judged", weight=1)
