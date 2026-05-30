# Context Kubernetes — formal abstractions (§3.2)

Exact tuple definitions. Read this when implementing an abstraction or when you need
a precise field, not just the intuition.

## Def 3.1 — Context Unit
`u = (c, τ, m, v, e, π)`
- `c` — content
- `τ ∈ {unstructured, structured, hybrid}` — type
- `m` — metadata set (author, timestamp, domain, sensitivity, entities, source)
- `v ∈ V` — version identifier
- `e ∈ R^d` — embedding vector
- `π ⊆ R` — set of roles authorized to access this unit (lives **on the unit**)

Authorization predicate: `role(α) ∈ π`.

## Def 3.2 — Context Domain
`D = (N, S, A, F, ρ, O, G)`
- `N` — domain identifier
- `S` — backing sources
- `A: R → 2^(Ops × Tier)` — access control function (role → {(operation, tier)})
- `F` — freshness policy
- `ρ` — routing configuration
- `O` — domain operator
- `G` — guardrail set

A query in `D_i` has **no** visibility into `D_j` unless brokered through `D_j`'s
operator with the requester's permissions propagated.

## Def 3.3 — Context Store
`s = (σ, ι, φ)`
- `σ` — store type (git repo, relational DB, connector, filesystem)
- `ι` — ingestion config
- `φ` — connection spec

Accessed **exclusively** through the CxRI.

## Def 3.4 — Context Endpoint
`ε(q, ω, α) → {u_1, ..., u_k} ⊆ U`
Given intent `q`, session scope `ω`, agent profile `α`, returns units satisfying:
`∀u_i: π(u_i) ∋ role(α) ∧ fresh(u_i) ∧ Σ|u_i| ≤ B` (token budget B).
The agent never specifies *where* — only *what*.

## Def 3.5 — Context Runtime Interface (CxRI)
Six operations every connector implements:
`connect(φ)→Connection`, `query(conn,q)→{u...}`, `read(conn,path)→u`,
`write(conn,path,c)→Result`, `subscribe(conn,path)→Stream`, `health(conn)→Status`.
Decouples the orchestrator from any data source (analogue of Kubernetes' CRI).

## Def 3.6 — Context Operator
`O = (K, L, I, Γ)`
- `K` — knowledge store (vector + full-text index)
- `L` — reasoning engine (LLM + domain guardrails)
- `I` — organizational intelligence module (pattern extraction; min signal θ ≥ 3)
- `Γ` — guardrail set

## Design invariants
- **3.7 Agent Permission Subset:** `P_au ⊂ P_u` (strict); for shared op `o`,
  `T(o, agent) ≥ T(o, user)`. Architectural — no API lets an agent widen its scope.
- **3.8 Strong Approval Isolation:** T3 approval channel is (1) external to the
  agent's execution env, (2) not readable/writable by the agent, (3) requires a
  separate authentication factor.

## Design goals (reconciliation loop)
- **3.9 Safety:** permission-safe (fail-closed if engine unavailable) + freshness-safe
  (never serve past-expired; serve stale only with explicit staleness metadata).
- **3.10 Liveness:** stale units re-synced/flagged within `2·Δt_r`; disconnected
  sources detected within `Δt_r`.
