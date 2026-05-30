"""Load and validate the eval suite (``evals.json`` + rubric extension).

The rubric is *additive*: the legacy ``prompt`` / ``expected_output`` fields are
preserved (as the human reference), and an optional ``rubric`` array makes each
eval scorable. A criterion is either:

  * ``deterministic`` — scored in Python by a named check (see ``checks.py``)
  * ``judged``        — scored by an LLM judge against a natural-language criterion
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Criterion(BaseModel):
    """One weighted line item of a rubric."""

    id: str
    kind: Literal["deterministic", "judged"]
    weight: float = Field(default=1.0, gt=0)
    # deterministic: the registered check name in checks.CHECKS
    check: str | None = None
    # judged: the natural-language criterion handed to the LLM judge
    criterion: str | None = None

    @model_validator(mode="after")
    def _require_kind_field(self) -> "Criterion":
        if self.kind == "deterministic" and not self.check:
            raise ValueError(f"deterministic criterion {self.id!r} needs a 'check' name")
        if self.kind == "judged" and not self.criterion:
            raise ValueError(f"judged criterion {self.id!r} needs a 'criterion' text")
        return self


class EvalCase(BaseModel):
    """A single eval: a prompt, a human reference answer, and a rubric."""

    id: int
    prompt: str
    expected_output: str = ""
    files: list[str] = Field(default_factory=list)
    rubric: list[Criterion] = Field(default_factory=list)


class EvalSuite(BaseModel):
    """The full benchmark suite for a skill."""

    skill_name: str
    evals: list[EvalCase]

    def case(self, case_id: int) -> EvalCase:
        for c in self.evals:
            if c.id == case_id:
                return c
        raise KeyError(f"no eval with id {case_id}")


def load_suite(path: str | Path) -> EvalSuite:
    """Parse and validate an ``evals.json`` file into an :class:`EvalSuite`."""
    data = json.loads(Path(path).read_text())
    return EvalSuite.model_validate(data)
