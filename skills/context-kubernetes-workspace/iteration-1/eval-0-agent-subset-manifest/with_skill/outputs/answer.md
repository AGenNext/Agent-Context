# Access control for internal LangGraph agents: an agent can only do a subset of what its owner can

Your two fears map onto two distinct controls, and it's worth keeping them separate in your head:

1. **"They'll see HR data they shouldn't"** → this is a *read-scoping + domain-isolation* problem. The fix is that an agent never gets blanket retrieval; it gets a read scope that is a subset of its human owner's, and HR lives in a separate isolation boundary that is denied by default.
2. **"They'll email clients without anyone checking"** → this is an *action-tier* problem. Sending an external email is a high-impact action that must require human approval through a channel the agent itself cannot touch.

Both of these fall out of one governing principle, which I'd recommend you adopt as a written rule:

> **Agent authority is a *strict* subset of human authority.** An agent acting for a user can never do anything the user can't, and for any action they share, the agent needs *at least as much* human oversight as the user would. "Strict" matters: there must be at least one thing the human can do that the agent cannot.

Paired with a second rule:

> **Fail closed.** If the system cannot positively confirm an agent is authorized for a piece of context or an action, it denies. Silence is denial, never permission.

Below is a concrete, version-controllable way to express this.

## The model in three layers

Think of it as three layers per knowledge domain (sales, HR, finance, etc.):

- **`access`** — the *human* RBAC. This is the ceiling. Whatever a human role can read/write/do.
- **`agentPermissions`** — what the agent gets. This **must be a strict subset** of `access`, and every operation is stamped with an oversight tier.
- **`crossDomain`** — which *other* domains this one can reach. Default-deny. HR is denied unless you deliberately broker it.

### The oversight tiers

Classify every agent action into one of four tiers:

| Tier | What the agent does | Approval required | Examples |
|---|---|---|---|
| **T1 Autonomous** | acts freely | none | read context it's scoped to, draft a doc |
| **T2 Soft approval** | proposes, user confirms in the agent UI | one click in-app | send an internal Slack/message |
| **T3 Strong approval** | surfaces the task, user approves out-of-band | separate auth factor (2FA / biometric), **outside the agent** | send an external/client email, move money, sign a contract |
| **Excluded** | cannot even request it | human does it manually, no agent path | terminate an employee, commit to pricing |

The rule of thumb (tier monotonicity): the more impactful the action, the higher the tier. External email and anything financial/contractual sit at **T3 or excluded** — never T1/T2.

### The one non-negotiable: T3 approval must be out-of-band

This is the part most platforms get wrong, and it's the one that actually protects you from a compromised or hallucinating agent. For any T3 action, the approval channel must be:

1. **External to the agent's execution environment** — the agent cannot read or write it.
2. **A separate authentication factor** — push notification to a phone, 2FA prompt, biometric. Not "the agent posts a question in the chat and reads the reply."

If the agent can read the approval back as a parameter, it can forge or fabricate it. A confused agent that has hijacked its own loop must not be able to self-approve sending a client email. So: in-band chat confirmation is fine for T2, but **never** for T3.

## Put this in version control

Express each domain as a declarative manifest — knowledge-architecture-as-code. Commit one file per domain, review changes via PR, and let your agent platform enforce it at runtime. Here is a complete `sales` domain manifest you can drop into a repo as-is and adapt:

```yaml
apiVersion: context/v1
kind: ContextDomain
metadata:
  name: sales
  namespace: acme-corp
  labels:
    sensitivity: confidential
    owner: head-of-sales

spec:
  # 1. SOURCES — backing stores, reached only via connectors (never raw DB access).
  sources:
    - name: client-context
      type: git-repo
      config: { repo: "git@ctx.internal:sales/clients.git" }
      refresh: realtime
    - name: pipeline
      type: connector
      config: { system: salesforce, scope: opportunities, credentials: "vault://sf/key" }
      refresh: 1h
    - name: communications
      type: connector
      config: { system: gmail, filter: "label:client-comms" }
      refresh: 15m

  # 2. ACCESS — HUMAN RBAC. This is the ceiling; agent perms must stay strictly under it.
  access:
    roles:
      - role: sales-rep
        read:  ["clients/${assigned}/*"]   # a rep sees only their assigned clients
        write: ["clients/${assigned}/*"]
      - role: sales-manager
        read:  ["*"]
        write: ["*"]

  # 3. AGENT PERMISSIONS — STRICT SUBSET of access, every op stamped with a tier.
  #    Note what's missing vs. the human: the agent can never commit to pricing,
  #    and external email always needs out-of-band approval. That's the "strict" part.
  agentPermissions:
    read: autonomous                        # reading scoped context is T1
    write:
      default: soft-approval                # routine writes: user confirms in UI
      paths:
        "*/contracts/*": strong-approval     # touching contracts: out-of-band approval
    execute:
      send-internal-msg:   soft-approval     # T2 — internal only
      send-external-email: strong-approval   # T3 — the client-email fear, gated out-of-band
      commit-to-pricing:   excluded          # the agent CANNOT do this at all

  # 4. CROSS-DOMAIN — default-deny. Anything not listed is denied.
  #    HR is explicitly denied, so a sales agent can never reach HR data.
  crossDomain:
    - { domain: finance, mode: brokered }    # allowed, but only via finance's operator
    - { domain: hr,      mode: denied }       # the HR-data fear, closed off explicitly

  # 5. FRESHNESS — every source bounded; never serve stale data silently.
  freshness:
    defaults: { maxAge: 24h, staleAction: flag }
    overrides:
      - { path: "*/communications/*", maxAge: 4h, staleAction: re-sync }
      - { path: "pipeline/*",          maxAge: 1h, staleAction: re-sync }

  # 6. ROUTING — agent asks for what it needs by intent, never names a store/path.
  routing:
    intentParsing: llm-assisted
    tokenBudget: 8000

  # 7. TRUST — guardrails, runtime policy, anomaly detection, and full audit.
  operator:
    type: master-agent
    guardrails:
      - "CANNOT commit to pricing without approval"
      - "CANNOT share clientA data with clientB"
      - "CANNOT read any HR-domain context"
  trust:
    policies:
      - name: no-unreviewed-external-email
        trigger: action.send_email
        condition: recipient.domain != company.domain   # any non-company recipient
        action: require_approval(tier: strong)           # forces out-of-band T3
    anomalyDetection: { baseline: per-user-per-role, threshold: 3x, response: alert-admin }
    audit: { level: full, retention: 7y }
```

And a separate, locked-down **HR** domain so the boundary is symmetric — HR denies sales right back, and even the HR agent cannot perform the most sensitive actions:

```yaml
apiVersion: context/v1
kind: ContextDomain
metadata:
  name: hr
  namespace: acme-corp
  labels:
    sensitivity: restricted
    owner: head-of-people

spec:
  sources:
    - name: employee-records
      type: connector
      config: { system: workday, credentials: "vault://hr/key" }
      refresh: 1h

  access:
    roles:
      - role: hr-business-partner
        read:  ["employees/${assigned-org}/*"]
        write: ["employees/${assigned-org}/*"]
      - role: hr-admin
        read:  ["*"]
        write: ["*"]

  agentPermissions:
    read:
      default: autonomous
      paths:
        "*/compensation/*": soft-approval      # comp data: even reads get a checkpoint
        "*/medical/*":      excluded            # agent can never read medical records
    write:
      default: soft-approval
    execute:
      send-internal-msg:  soft-approval
      terminate-employee: excluded              # never an agent action — human only
      change-compensation: excluded

  crossDomain:
    - { domain: sales,   mode: denied }
    - { domain: finance, mode: denied }

  freshness:
    defaults: { maxAge: 12h, staleAction: flag }

  routing:
    intentParsing: llm-assisted
    tokenBudget: 6000

  trust:
    guardrails:
      - "CANNOT expose PII outside the hr domain"
    audit: { level: full, retention: 7y }
```

## How LangGraph plugs into this

You don't enforce this *inside* the LangGraph graph — you enforce it at the boundary the graph talks to, so a buggy or jailbroken graph can't talk its way around it:

- **Reads:** the agent's retrieval/tool node never queries a vector store or DB directly. It calls a single "context endpoint" with an *intent* ("get me the context for client Acme's renewal") plus the agent's profile (which carries its owner's identity and role). The endpoint resolves which sources/units to return, filters them against `agentPermissions.read` and the unit's own access scope, applies freshness, and trims to the token budget. The agent never specifies *where* — only *what*. HR units simply never come back to a sales agent.
- **Actions/writes:** every tool that mutates state or sends a message routes through a permission check that returns one of: allow (T1), enqueue-for-soft-approval (T2), enqueue-for-strong-approval (T3), or deny/excluded. For T3, the LangGraph run **pauses** (use an interrupt / checkpoint) and the approval request is dispatched to the out-of-band channel — a push to the owner's phone, a 2FA prompt — and the run only resumes on a signed approval that the graph itself never had write access to.
- **Fail-closed:** if the permission engine is unreachable, the tool call denies rather than proceeds.

## Before you ship: the validation checklist

Run every domain manifest through this in PR review:

- [ ] **Strict subset.** Is there at least one operation a human role can do that the agent cannot? (Here: `commit-to-pricing` / `terminate-employee` are excluded, and external email needs approval the human wouldn't.) If `agentPermissions` mirrors `access` exactly, you've violated the core invariant — withhold or downgrade something.
- [ ] **Tier monotonicity.** Does every high-impact action (external email, financial, contractual, termination) sit at `strong-approval` or `excluded`? Reads of scoped data can be autonomous.
- [ ] **Cross-domain default-deny.** Is every domain *not* listed treated as denied? HR should never be implicitly reachable. Spell out the deny.
- [ ] **Freshness has teeth.** Does every source have a `maxAge` and a `staleAction`? Stale-but-served-silently is a top failure mode.
- [ ] **Strong-approval isolation.** For every T3 action, is the approval channel out-of-band — something the agent cannot read back, requiring a separate auth factor? In-band chat confirmation does not count.
- [ ] **Audit.** Is every access, action, and approval logged with attribution (which agent, on behalf of which human) and outcome, with a retention you can defend to compliance?

## Things to push back on internally

If anyone proposes these, they reintroduce exactly the risks you're worried about:

- *"Just give the agent the same permissions as its owner."* That violates the strict-subset rule and is how the agent ends up doing things no one would have signed off on. Reframe: which one capability do we withhold, and which actions need approval?
- *"The agent will just ask in chat and the user replies there."* That's not isolation for high-stakes actions — the agent can read, fabricate, or be tricked into the reply. Fine for internal T2; never for client emails or money.
- *"Give it access to everything and we'll filter later."* Fail-open is the opposite of what protects you. Start default-deny and open access deliberately, domain by domain.

Start with the two manifests above in a `context-domains/` directory in a repo, gate changes behind PR review, and grow one domain at a time.
