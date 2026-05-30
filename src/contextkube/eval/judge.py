"""LLM judge for ``judged`` rubric criteria.

Talks to an OpenAI-compatible endpoint (the LiteLLM gateway). Model, base URL,
and key are read from the environment — never hardcoded:

    EVAL_JUDGE_MODEL      e.g. "gpt-oss-120b"  (whatever the gateway exposes)
    EVAL_JUDGE_BASE_URL   e.g. "https://llm.openautonomyx.com/v1"
    EVAL_JUDGE_API_KEY

The judge returns a strict ``{passed, confidence, rationale}`` per criterion.
Scoring code depends only on the ``Judge`` protocol, so tests inject a stub and
never hit the network.
"""

from __future__ import annotations

import json
import os
from typing import Protocol

from pydantic import BaseModel


class JudgeVerdict(BaseModel):
    passed: bool
    confidence: float = 1.0  # in [0, 1]
    rationale: str = ""


class Judge(Protocol):
    def __call__(self, *, criterion: str, prompt: str, candidate: str) -> JudgeVerdict: ...


_SYSTEM = (
    "You are a strict evaluator for AI-governance answers (Context Kubernetes). "
    "Given a user PROMPT, a CANDIDATE answer, and a single CRITERION, decide "
    "whether the candidate satisfies that criterion. Judge only the stated "
    "criterion. Respond with ONLY a JSON object: "
    '{"passed": bool, "confidence": number between 0 and 1, "rationale": short string}.'
)


def _build_user_msg(criterion: str, prompt: str, candidate: str) -> str:
    return (
        f"PROMPT:\n{prompt}\n\n"
        f"CANDIDATE:\n{candidate}\n\n"
        f"CRITERION:\n{criterion}\n\n"
        "Return the JSON verdict now."
    )


class GatewayJudge:
    """Default judge: POST /chat/completions to the configured gateway."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model or os.environ.get("EVAL_JUDGE_MODEL")
        self.base_url = (base_url or os.environ.get("EVAL_JUDGE_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("EVAL_JUDGE_API_KEY", "")
        if not self.model or not self.base_url:
            raise RuntimeError(
                "GatewayJudge needs EVAL_JUDGE_MODEL and EVAL_JUDGE_BASE_URL "
                "(set them or pass a stub judge to the scorer)."
            )

    def __call__(self, *, criterion: str, prompt: str, candidate: str) -> JudgeVerdict:
        import requests  # local import: only needed when actually judging

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": _build_user_msg(criterion, prompt, candidate)},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _parse_verdict(content)


def _parse_verdict(content: str) -> JudgeVerdict:
    """Best-effort parse of the model's JSON verdict."""
    text = content.strip()
    # tolerate ```json fences
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return JudgeVerdict(passed=False, confidence=0.0, rationale=f"unparseable judge output: {content[:200]}")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return JudgeVerdict(passed=False, confidence=0.0, rationale=f"invalid JSON from judge: {content[:200]}")
    conf = float(data.get("confidence", 1.0))
    return JudgeVerdict(
        passed=bool(data.get("passed", False)),
        confidence=max(0.0, min(1.0, conf)),
        rationale=str(data.get("rationale", "")),
    )
