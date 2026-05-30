# AgentKube — Context Kubernetes

A prototype implementation of **Context Kubernetes** — declarative orchestration of
enterprise knowledge for agentic AI systems, after Mouzouni (2026),
*"Context Kubernetes: Declarative Orchestration of Enterprise Knowledge for Agentic
AI Systems"* (arXiv:2604.11623).

The thesis: delivering *the right knowledge, to the right agent, with the right
permissions, at the right freshness, within the right cost* — across an organization —
is structurally the container-orchestration problem Kubernetes solved, applied to
knowledge.

## What's here

```
src/contextkube/
├── core/models.py         # the six core abstractions (§3.2), encoded from the formal defs
└── permissions/engine.py  # three-tier permission model + Invariant 3.7 (agent ⊂ human), fail-closed

skills/context-kubernetes/ # an Agent Skill that teaches/enforces the model:
├── SKILL.md               #   principles, abstractions, manifest skeleton, validation checklist
├── references/            #   formal definitions + a worked ContextDomain manifest
└── evals/                 #   triggering + scoring eval set
```

## Core invariants

- **Agent authority is a strict subset of human authority** (Design Invariant 3.7):
  `P_agent ⊂ P_user`, strictly, with shared ops requiring ≥ the human's oversight tier.
- **Fail-closed**: if authorization cannot be positively confirmed, deny.
- **Strong-approval isolation** (Design Invariant 3.8): high-stakes (Tier 3) approvals
  happen out-of-band, on a channel the agent cannot read or write.

## Status

Prototype / reference implementation. Not production-grade. See the paper for the full
architecture (Context Router, Freshness Manager, reconciliation loop, etc.).
