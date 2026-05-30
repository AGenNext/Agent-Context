# AgentKube-ContextGov-v0 Leaderboard

Benchmark for the [`context-kubernetes`](../skills/context-kubernetes) skill —
measuring how well an LLM agent governs knowledge access for AI agents using
the Context Kubernetes framework (Mouzouni, 2026).

## How to reproduce

```bash
pip install -e ".[eval]"

# deterministic-only (no judge, fully reproducible):
contextkube-eval \
  --suite skills/context-kubernetes/evals/evals.json \
  --candidates your_answers.json \
  --no-judge

# full (deterministic + LLM judge via gateway):
EVAL_JUDGE_MODEL=<model> \
EVAL_JUDGE_BASE_URL=<url> \
EVAL_JUDGE_API_KEY=<key> \
  contextkube-eval \
  --suite skills/context-kubernetes/evals/evals.json \
  --candidates your_answers.json \
  --out report.md
```

`your_answers.json` format: `{"1": "<answer text>", "2": "...", "3": "..."}`

## Metric

**Hybrid score** (see [design spec](../docs/superpowers/specs/2026-05-30-agentkube-eval-metric-benchmark-design.md)):
- **Deterministic** criteria: machine-checked against `src/contextkube/permissions/engine.py` invariants. Reproducible, model-independent.
- **Judged** criteria: LLM judge via OpenAI-compatible gateway. Scores reasoning and pushback quality.
- **Total** = weighted sum normalized to [0, 1]. **Det-only** = deterministic backbone only.

## Results

| Date | Candidate | Judge Model | Total ↑ | Det-only ↑ | Notes |
|---|---|---|---:|---:|---|
| 2026-05-30 | Gold reference answers | — (det only) | 100.0% | **100.0%** | Handcrafted fully-compliant answers; establishes ceiling for deterministic criteria |
| _pending_ | Any model | gateway model | — | — | Run `contextkube-eval` with your model's answers and PR a row |

> **Note:** Judged criteria (evals #1 explains-subset-invariant, #2 freshness-states + no-silent-stale, #3 pushes-back-inband + explains-3.8 + classifies-t3) require a configured judge gateway. The deterministic sub-score is the reproducible backbone and will not drift between runs.

## Eval breakdown (v0 — 3 evals)

| Eval | Topic | Deterministic criteria | Judged criteria |
|---|---|---|---|
| #1 | Agent RBAC manifest | parses-as-ContextDomain, strict-subset (×2), crossdomain-deny, tier-monotonicity | explains-subset-invariant (×2) |
| #2 | Freshness & stale knowledge | freshness-has-teeth | freshness-states (×2), no-silent-stale (×2) |
| #3 | Wire-transfer approval safety | — | pushes-back-inband (×2), explains-3.8-isolation (×2), classifies-t3 |

## Submitting a result

1. Run `contextkube-eval` with your model's answers (full run with a judge, or det-only).
2. Open a PR adding a row to the Results table above.
3. Include the `report.md` output as a file under `benchmarks/results/YYYY-MM-DD-<model>.md`.

---
_AgentKube-ContextGov-v0 · AgentNxt / Autonomyx · [Feedback](https://www.openautonomyx.com/feedback)_
_AI-generated evaluation — verify before relying on scores._
