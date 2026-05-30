# AgentKube — Eval Metric & Published Benchmark (v0)

**Date:** 2026-05-30
**Status:** Draft for review
**Scope:** A scoring metric for the `context-kubernetes` skill's evals, plus a publishable benchmark (`AgentKube-ContextGov-v0`).

---

## 1. Goal

Turn `skills/context-kubernetes/evals/evals.json` (today: bare `prompt` + prose
`expected_output`, no scoring) into:

1. A **reproducible eval metric** that scores a candidate answer in `[0, 1]`.
2. A **published benchmark** others can run and submit to, with a leaderboard.

Non-goals (v0): training/fine-tuning, multi-turn agent traces, a hosted web UI,
expanding the eval set beyond the existing 3 (expansion is a fast-follow).

---

## 2. Metric — Hybrid (deterministic checks + LLM-judge rubric)

Each eval is scored against a **rubric**: a list of weighted criteria. Every
criterion is one of two kinds:

- **`deterministic`** — evaluated by Python. For manifest outputs we parse the
  YAML and reuse `src/contextkube/`:
  - manifest parses into a `ContextDomain` (pydantic validates structure)
  - `agentPermissions ⊊ access` via `PermissionEngine.verify_subset`
  - cross-domain default-deny: every referenced domain is explicitly `denied`
    or `brokered` (no implicit allow)
  - freshness has teeth: every source has `maxAge` **and** `staleAction`
  - tier monotonicity: high-impact ops (external email, financial, contractual)
    sit at `strong-approval` or `excluded` (via `tier_rank`)
- **`judged`** — evaluated by an LLM judge for reasoning/pushback the structure
  can't capture, e.g. "explains Invariant 3.8 out-of-band isolation",
  "pushes back on in-band chat approval", "names the strict-subset invariant".

### Score

```
eval_score   = Σ_c (weight_c · pass_c)      where  pass_c ∈ {0, 1} (det.)
                                                    pass_c ∈ [0, 1] (judged, judge-confidence)
             normalized so Σ weight_c = 1   ⇒ eval_score ∈ [0, 1]
benchmark    = mean(eval_score over all evals)
report       = benchmark score + per-criterion pass/fail table + judge rationales
```

The per-criterion table (CLEAR-style textual insight) is the primary artifact —
not just the scalar. Each failing criterion links back to the offending part of
the candidate output.

### Judge

- Default judge = **local model via the LiteLLM gateway** (`llm.openautonomyx.com`,
  model from config/env — never hardcoded). Cheap, owns the bulk scoring.
- Optional **strong-model judge** for periodic deep dives (local judges score
  fine but name failures less richly — observed in the CLEAR/Agentic-CLEAR papers).
- Judge prompt asks for `{pass: bool, confidence: 0..1, rationale: str}` per
  `judged` criterion. Deterministic criteria never touch the judge.

---

## 3. Rubric data format

Extend each entry in `evals.json` with a `rubric` (backward-compatible — the
existing `prompt`/`expected_output` stay):

```jsonc
{
  "id": 1,
  "prompt": "...",
  "expected_output": "...",          // kept as human reference
  "rubric": [
    { "id": "manifest-parses",   "kind": "deterministic", "check": "parses_as_context_domain", "weight": 1 },
    { "id": "strict-subset",     "kind": "deterministic", "check": "agent_perms_strict_subset", "weight": 2 },
    { "id": "crossdomain-deny",  "kind": "deterministic", "check": "crossdomain_default_deny",  "weight": 1 },
    { "id": "freshness-teeth",   "kind": "deterministic", "check": "freshness_has_teeth",       "weight": 1 },
    { "id": "explains-3.8",      "kind": "judged", "criterion": "Explains that T3 approval must be out-of-band, not agent-readable, separate auth factor", "weight": 2 }
  ]
}
```

`check` names map to functions in a registry (§4). Evals with no manifest (e.g.
#3 pushback) use mostly/all `judged` criteria.

---

## 4. Components / files

```
src/contextkube/eval/
  __init__.py
  loader.py        # load evals.json, validate rubric schema (pydantic)
  checks.py        # deterministic check registry: name -> fn(candidate, ctx) -> bool
  judge.py         # LLM judge client (gateway, OpenAI-compatible), config-driven model
  rubric.py        # scoring: combine det + judged criteria -> eval_score, report
  runner.py        # CLI: run a candidate (or model) over the benchmark, emit report
  report.py        # render per-criterion table (markdown/json) + AI disclaimer/attribution
tests/eval/
  test_checks.py   # deterministic checks on golden good/bad manifests (TDD)
  test_rubric.py   # scoring math, weight normalization, edge cases
```

- `checks.py` reuses `core/models.py` + `permissions/engine.py`; it adds **no**
  new permission logic, only adapts parsed manifests to existing calls.
- Judge model id, base URL, and API key come from env/config (no hardcoding).

---

## 5. Publishing the benchmark — `AgentKube-ContextGov-v0`

- **Dataset:** publish the eval set (prompt + rubric + reference output) as a
  **HuggingFace dataset** under the org account.
- **Leaderboard:** a `benchmarks/leaderboard.md` in this repo — versioned table
  of `(model, judge, benchmark score, per-criterion breakdown, date)`. Runner
  appends a row.
- **Reproducibility:** the deterministic half is model-independent, so two runs
  of the same candidate differ only in the `judged` portion — report both the
  total and the deterministic-only sub-score (the stable backbone).
- **Branding:** published artifacts carry the standard AI disclaimer +
  AgentNxt/Autonomyx attribution + feedback link.

> **Decision needed from you:** publish to HuggingFace, the repo leaderboard, or
> both? Spec currently assumes *both*. GitHub structure change → your call.

---

## 6. Build order (for the implementation plan)

1. Rubric schema + loader (pydantic) — TDD.
2. Deterministic check registry, tested against golden good/bad manifests.
3. Scoring/`rubric.py` — weight normalization + combine.
4. Judge client (gateway) — mockable in tests.
5. Runner CLI + report renderer.
6. Backfill `rubric` arrays for the 3 existing evals.
7. Publish dataset + seed leaderboard with a baseline run.

---

## 7. Locked decisions

1. Metric approach: **A (hybrid)** — locked.
2. Publish targets: **HuggingFace dataset + repo leaderboard, both** — locked.
   External publish (HF upload / leaderboard commit) requires one confirmation
   before execution; local harness does not.
3. v0 scope: **wire up the existing 3 evals** end-to-end — locked.
4. Judge model: **config-driven via the LiteLLM gateway**, read from env
   `EVAL_JUDGE_MODEL` + `EVAL_JUDGE_BASE_URL` (no hardcoded model names/URLs).
   Baseline leaderboard row seeded with whatever model the gateway exposes at
   run time.
