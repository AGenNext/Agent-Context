---
name: context-kubernetes
description: >-
  Declarative orchestration of enterprise knowledge for agentic AI systems — the
  "Kubernetes for context." Use this skill whenever the user wants to govern what
  knowledge their AI agents can access, set up permissions or RBAC for agents,
  control freshness/staleness of agent context, design knowledge-architecture-as-code,
  author or validate a ContextDomain manifest, or prevent agents from leaking
  cross-domain data, serving stale/phantom content, or self-approving high-stakes
  actions. Trigger even when the user doesn't say "Context Kubernetes" — phrases
  like "my agents can see too much", "how do I scope what the LLM retrieves",
  "governance for our agent platform", "agent permissions vs user permissions",
  "RAG access control", "knowledge orchestration", or "approval gates for agent
  actions" all apply. Also use when working in the AgentKube prototype.
---

# Context Kubernetes

Orchestrate organizational knowledge for AI agents the way Kubernetes orchestrates
containers: **declare** the desired knowledge architecture, and let a reconciliation
loop converge reality to match. The job is delivering the *right knowledge, to the
right agent, with the right permissions, at the right freshness, within the right
cost* — across a whole organization.

This skill helps you do four things, in roughly this order:

1. **Diagnose** what governance the situation needs (permissions? freshness? isolation?).
2. **Author** a declarative `ContextDomain` manifest (knowledge-architecture-as-code).
3. **Enforce** the three-tier agent permission model and the core invariants.
4. **Validate** the manifest and reason about what could go wrong without it.

## The core principle to anchor on

**Agent authority is a *strict* subset of human authority** (Design Invariant 3.7).
An agent acting for a user can never do something the user can't, and for any shared
action it needs *at least as much* human oversight as the user would. If you remember
one thing, remember this — it's the property that prevents the failure modes this
whole discipline exists to stop.

The second anchor: **fail-closed**. If you cannot positively confirm an agent is
authorized for a piece of context, deny it. Silence is denial, never permission.

## The six abstractions (vocabulary)

When reasoning about a knowledge landscape, decompose it into these. Don't invent
new nouns — map the user's situation onto these six.

| Abstraction | What it is | One-line test |
|---|---|---|
| **Context Unit** | smallest addressable knowledge element; carries its own access scope π | "who is allowed to see this?" |
| **Context Domain** | isolation boundary (e.g. `sales`, `hr`); no cross-domain visibility unless brokered | "what's the blast radius?" |
| **Context Store** | a backing system (git, DB, SaaS connector), reached only via the CxRI | "where does it physically live?" |
| **Context Endpoint** | intent-based access: agent asks *what* it needs, never *where* | "what does the agent want?" |
| **CxRI** | the 6-op connector contract (`connect/query/read/write/subscribe/health`) | "how do we talk to the source?" |
| **Context Operator** | domain-specific controller that adds intelligence + guardrails | "who governs this domain?" |

Full formal definitions live in `references/abstractions.md` — read it when you need
the exact tuple fields or are implementing one of these.

## The three-tier permission model

Every agent action is classified into a tier of required human oversight:

| Tier | Agent role | Approval | Examples |
|---|---|---|---|
| **T1 Autonomous** | acts freely | none | read context, draft a doc |
| **T2 Soft approval** | proposes | user confirms in agent UI | send internal message |
| **T3 Strong approval** | surfaces task | **out-of-band** 2FA/biometric | sign contract, move money |
| **Excluded** | cannot request | manual only | terminate an employee |

**The non-negotiable for T3 (Design Invariant 3.8):** the approval channel must be
*external to the agent's execution environment* — not readable or writable by the
agent — and require a *separate authentication factor*. A compromised or hallucinating
agent must not be able to self-approve. This is the gap no major platform closes; if
you're designing approvals, this is where you add real value.

## Authoring a ContextDomain manifest

The deliverable for most requests is a YAML manifest. Use this skeleton and fill the
seven sections (`sources`, `access`, `agentPermissions`, `crossDomain`, `freshness`,
`routing`, `operator`/`trust`). Apply the trust ladder: more impactful operations
demand higher tiers.

```yaml
apiVersion: context/v1
kind: ContextDomain
metadata:
  name: sales
  namespace: acme-corp
  labels: { sensitivity: confidential, owner: head-of-sales }
spec:
  sources:
    - name: client-context
      type: git-repo
      config: { repo: "git@ctx.internal:sales/clients.git" }
      refresh: realtime
  access:                       # human RBAC — the ceiling
    roles:
      - role: sales-rep
        read:  ["clients/${assigned}/*"]
        write: ["clients/${assigned}/*"]
  agentPermissions:             # MUST be a strict subset of access, with tiers
    read: autonomous
    write:
      default: soft-approval
      paths: { "*/contracts/*": strong-approval }
    execute:
      send-internal-msg: soft-approval
      send-external-email: strong-approval
      commit-to-pricing: excluded
  crossDomain:                  # default-deny; name only what's brokered
    - { domain: finance, mode: brokered }
    - { domain: hr, mode: denied }
  freshness:
    defaults: { maxAge: 24h, staleAction: flag }
    overrides:
      - { path: "*/communications/*", maxAge: 4h, staleAction: re-sync }
  routing:
    intentParsing: llm-assisted
    tokenBudget: 8000
  trust:
    audit: { level: full, retention: 7y }
```

A representative complete manifest is in `references/manifest-example.yaml`.

## Validation checklist

Before you hand back any manifest or design, walk this list explicitly. These are the
exact things that go wrong in practice (and that the paper's experiments measured):

- [ ] **Strict subset:** is there at least one operation a human role can do that the
      agent cannot? If `agentPermissions` mirrors `access` exactly, the invariant is
      violated — drop or exclude something.
- [ ] **Tier monotonicity:** does every high-impact action (external email, financial,
      contractual) sit at `strong-approval` or `excluded`? Reads can be autonomous.
- [ ] **Cross-domain default-deny:** is every domain *not* listed treated as denied?
      Never leave cross-domain access implicit.
- [ ] **Freshness has teeth:** does every source have a `maxAge` and a `staleAction`?
      Stale-but-served-silently is a top failure mode.
- [ ] **Strong-approval isolation:** for any T3 action, is the approval channel
      out-of-band (not something the agent can read back as a parameter)?
- [ ] **Audit:** is every access/action/approval logged with attribution + outcome?

## Working in the AgentKube prototype

If the user is in `/Users/apple/AgentKube` (or its `Agent-Context` repo), there's a
Python implementation of these abstractions under `src/contextkube/`. Map manifest
concepts to code: `core/models.py` holds the six abstractions, `permissions/engine.py`
holds the three-tier model and the `verify_subset` / fail-closed `check_access` logic.
Prefer extending those modules over inventing parallel structures.

## What to push back on

- A request to give an agent the *same* permissions as its user → violates Invariant 3.7.
  Reframe: which one capability will you withhold, and which actions need approval?
- An in-band approval ("the agent asks, the user replies in chat") for a high-stakes
  action → explain why that's not real isolation (the agent can read/forge the reply).
- "Just give the agent access to everything and we'll filter later" → fail-open is the
  opposite of this skill's stance; start default-deny and open deliberately.
