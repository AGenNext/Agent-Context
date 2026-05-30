# Eval report — context-kubernetes

**Benchmark score:** 100.0%  
**Deterministic-only (reproducible) score:** 100.0%

## Eval #1 — 100.0% (deterministic 100.0%)

| Criterion | Kind | Weight | Score | Detail |
|---|---|---:|---:|---|
| manifest-parses | deterministic | 1 | 1.00 | valid ContextDomain manifest found |
| strict-subset | deterministic | 2 | 1.00 | strict subset: excludes at least one action |
| crossdomain-deny | deterministic | 1 | 1.00 | 2 cross-domain relations all brokered/denied |
| tier-monotonicity | deterministic | 1 | 1.00 | all high-impact actions are strong-approval/excluded |

## Eval #2 — 100.0% (deterministic 100.0%)

| Criterion | Kind | Weight | Score | Detail |
|---|---|---:|---:|---|
| freshness-policy-block | deterministic | 1 | 1.00 | freshness defaults set: {'maxAge': '24h', 'staleAction': 'flag'} |

---
_AI-generated evaluation by AgentNxt / Autonomyx. Scores are produced by automated checks and an LLM judge — verify before relying on them. Feedback: https://www.openautonomyx.com/feedback_