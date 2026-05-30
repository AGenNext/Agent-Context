---
license: apache-2.0
task_categories:
  - text-generation
  - question-answering
language:
  - en
tags:
  - agent-evaluation
  - context-governance
  - rbac
  - llm-agents
  - agentic-ai
  - benchmark
  - context-kubernetes
pretty_name: AgentKube-ContextGov-v0
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files:
      - split: test
        path: data/evals.json
---

# AgentKube-ContextGov-v0

**Benchmark for evaluating LLM agent knowledge-governance skills** — measuring how well
a model applies the [Context Kubernetes](https://arxiv.org/abs/2605.XXXXX) framework
to govern what AI agents can access, at what permission tier, with what freshness guarantees.

## Why this benchmark exists

Context Kubernetes (Mouzouni, 2026) introduces a formal governance model for agentic AI:
declarative `ContextDomain` manifests, a three-tier permission model (autonomous / soft-approval /
strong-approval / excluded), fail-closed routing, and freshness policies. Current LLM evaluations
don't test whether models can correctly *apply* these governance invariants.

AgentKube-ContextGov-v0 fills that gap with a hybrid metric:
- **Deterministic criteria** — machine-checked against the formal invariants (strict-subset, cross-domain default-deny, tier monotonicity, freshness teeth). Reproducible, model-independent.
- **Judged criteria** — LLM judge scores reasoning quality, pushback behavior, and invariant explanation.

## Dataset structure

Three evaluation cases, each with a `prompt`, a `rubric` of weighted criteria, and a reference `expected_output`.

| Eval | Topic | Deterministic criteria | Judged criteria |
|---|---|---|---|
| 1 | Agent RBAC manifest | parses-as-ContextDomain, strict-subset (×2), crossdomain-deny, tier-monotonicity | explains-subset-invariant (×2) |
| 2 | Freshness & stale knowledge | freshness-has-teeth | freshness-states (×2), no-silent-stale (×2) |
| 3 | Wire-transfer approval safety | — | pushes-back-inband (×2), explains-3.8-isolation (×2), classifies-t3 |

## Scoring

```
eval_score = Σ (weight_c × pass_c) / Σ weight_c   ∈ [0, 1]
benchmark  = mean(eval_score) over all evals
```

Deterministic pass = 1.0/0.0. Judged pass = judge confidence (partial credit). A
separate deterministic-only sub-score is always reported as the reproducible backbone.

## Running the benchmark

```bash
# Install
git clone https://github.com/AGenNext/AgentAid
cd AgentAid
pip install -e ".[eval]"

# Run (deterministic only — no judge needed)
contextkube-eval \
  --suite skills/context-kubernetes/evals/evals.json \
  --candidates your_answers.json \
  --no-judge

# Run (full — requires EVAL_JUDGE_* env vars)
EVAL_JUDGE_MODEL=<model> \
EVAL_JUDGE_BASE_URL=<litellm-gateway-url>/v1 \
EVAL_JUDGE_API_KEY=<key> \
  contextkube-eval \
  --suite skills/context-kubernetes/evals/evals.json \
  --candidates your_answers.json \
  --out report.md
```

`your_answers.json` format: `{"1": "<answer text>", "2": "...", "3": "..."}`

## Leaderboard

See [`benchmarks/leaderboard.md`](https://github.com/AGenNext/AgentAid/blob/main/benchmarks/leaderboard.md)
in the source repo.

## Citation

```bibtex
@misc{agentkube-contextgov-v0,
  title  = {AgentKube-ContextGov-v0: A Benchmark for LLM Agent Knowledge Governance},
  author = {AgentNxt / Autonomyx},
  year   = {2026},
  url    = {https://huggingface.co/datasets/AGenNext/AgentKube-ContextGov-v0}
}
```

---
*AgentNxt / Autonomyx · [Feedback](https://www.openautonomyx.com/feedback)*
*AI-assisted benchmark — verify before relying on scores.*
