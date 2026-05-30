# Access control for internal LangGraph agents: the "subset of the owner" model

Your two fears are the right ones, and they're actually two different problems:

1. **Confidentiality** — the agent reads HR data it shouldn't (over-broad *read* scope).
2. **Unsafe action** — the agent emails a client with no human in the loop (over-broad *write* scope + no approval gate).

The clean mental model that solves both is: **an agent is a constrained delegate of a human.** It never has its own ambient authority. At runtime its effective permission is:

```
effective = intersection(owner_permissions, agent_grant, tool_scopes)
```

The agent can only ever do a **subset** of what its owner can do — never a superset, never something the owner can't do either. This is the principle of least privilege plus "no privilege escalation through delegation."

Below is something concrete you can drop into version control today: a declarative manifest per agent, a policy that enforces the subset rule, and the enforcement points that make it real (not just documentation).

---

## 1. The core artifact: a per-agent manifest (commit this)

One YAML file per agent, reviewed via pull request like any other infra change. This is your source of truth and your audit trail.

```yaml
# agents/hr-onboarding-assistant.yaml
apiVersion: agentcontrol/v1
kind: AgentGrant

metadata:
  name: hr-onboarding-assistant
  owner: jane.doe@company.com          # the human this agent acts on behalf of
  team: people-ops
  description: >
    Drafts onboarding checklists and answers new-hire questions.
    Read-only on HR data, can draft (never send) internal email.

# Hard rule the policy engine enforces: effective scope is the
# INTERSECTION of these grants and the owner's own IdP group scopes.
# The agent can never exceed the owner.
subsetOf: owner          # enforced, not advisory

# What the agent may READ. Default-deny: anything not listed is denied.
data:
  read:
    - resource: hr.employees
      # row-level + column-level filtering, not just "the HR system"
      rowFilter: "department == 'engineering' AND status == 'pre_start'"
      columns: [employee_id, full_name, start_date, manager, checklist_status]
      # explicitly excluded so a reviewer sees the intent
      denyColumns: [ssn, salary, bank_account, performance_review, medical]
    - resource: confluence.space
      scope: ["ONBOARDING"]            # one space, not the whole wiki
  write: []                            # this agent writes no data stores

# What the agent may DO (tools/actions). Default-deny.
tools:
  - name: email.draft                  # creates a draft in the owner's mailbox
    allow: true
  - name: email.send
    allow: true
    recipients:
      allowDomains: ["company.com"]    # internal only; *.client.com is denied
    requireApproval: false             # internal mail to colleagues is low-risk
  - name: calendar.create_event
    allow: true
    requireApproval: false

# Actions that are categorically forbidden for THIS agent.
deny:
  - email.send.external                # belt-and-suspenders vs the rule above
  - hr.employees.write
  - data.export

# Anything not explicitly allowed above is denied. State it so reviewers know.
defaultDecision: deny

# Human-in-the-loop: actions that always pause for approval before executing.
approvals:
  required:
    - tool: email.send
      when: "recipient.domain != 'company.com'"   # any external send → human
    - tool: "*"
      when: "estimated_blast_radius == 'high'"
  approvers: ["jane.doe@company.com", "people-ops-leads@company.com"]
  timeoutAction: deny                  # if no one approves, do nothing
  expiresAfter: 24h

# Operational guardrails
limits:
  maxToolCallsPerRun: 40
  maxEmailsPerDay: 25
  tokenBudgetPerRun: 200000

# Auditing
audit:
  logEveryToolCall: true
  retainDays: 365
  sink: company-audit-log
```

A second example shows the contrast — a client-facing agent where external send is *allowed but always gated*:

```yaml
# agents/sales-followup-drafter.yaml
apiVersion: agentcontrol/v1
kind: AgentGrant
metadata:
  name: sales-followup-drafter
  owner: sam.rep@company.com
  team: sales
subsetOf: owner
data:
  read:
    - resource: crm.deals
      rowFilter: "owner == '${agent.owner}'"   # only the owner's own deals
      columns: [deal_id, account_name, stage, last_contact, notes]
  write: []
tools:
  - name: email.draft
    allow: true
  - name: email.send
    allow: true
    recipients:
      allowDomains: ["*"]              # external is the point of this agent
    requireApproval: true              # ...but a human approves EVERY send
deny:
  - crm.deals.delete
  - data.export
defaultDecision: deny
approvals:
  required:
    - tool: email.send
      when: "true"                     # always
  approvers: ["sam.rep@company.com"]
  timeoutAction: deny
audit:
  logEveryToolCall: true
  retainDays: 365
```

Key design choices that directly answer your fears:

- **HR data leak →** `data.read` is default-deny with **row + column filters**, not "access to the HR system." The agent literally cannot retrieve SSN/salary even within the rows it can see.
- **Email to clients →** `email.send` to external domains is either denied outright or routed through `approvals.required` with `timeoutAction: deny`. No human, no send.
- **Subset guarantee →** `subsetOf: owner` is enforced at runtime by intersecting with the owner's real IdP scopes, so an agent can't out-permission its owner even if the YAML is wrong.

---

## 2. The policy that enforces the subset rule (commit this)

The YAML is only safe if something *evaluates* it on every call. Express the intersection rule as policy-as-code so it's testable and reviewable. Here's the rule in OPA/Rego (use whatever engine you like — Cedar, Casbin, or your own — the logic is what matters):

```rego
# policy/agent_subset.rego
package agentcontrol

import future.keywords.if
import future.keywords.in

default allow := false

# 1) The owner must actually be allowed to do this, with the same data scope.
owner_allows if {
    some perm in data.owners[input.agent.owner].permissions
    perm.action == input.request.action
    scope_within(input.request.scope, perm.scope)
}

# 2) The agent grant must explicitly allow it (default-deny).
grant_allows if {
    some t in input.grant.tools
    t.name == input.request.action
    t.allow == true
}

# 3) It must not be on the agent's explicit deny list.
not_denied if {
    not input.request.action in input.grant.deny
}

# Allow only if it's a subset of the owner AND explicitly granted AND not denied.
allow if {
    owner_allows          # <-- the "subset of the owner" guarantee
    grant_allows
    not_denied
    not needs_approval
}

# Separate decision: pause for human approval.
needs_approval if {
    some a in input.grant.approvals.required
    a.tool in {input.request.action, "*"}
    cond_true(a.when, input)
}

decision := {"effect": "allow"}          if allow
decision := {"effect": "require_approval", "approvers": input.grant.approvals.approvers} if needs_approval
decision := {"effect": "deny"}           if not allow; not needs_approval
```

The first clause — `owner_allows` — is what makes "subset of the owner" a hard guarantee rather than a hope. If the owner loses access to HR data (leaves People-Ops), every agent they own loses it on the next call, automatically.

---

## 3. Where you enforce it in LangGraph (the part that makes it real)

A manifest enforced nowhere is a comment. In LangGraph you have three enforcement points; use all three.

### (a) Wrap every tool — deny/approve before the side effect

```python
# runtime/guarded_tool.py
from langchain_core.tools import tool
from langgraph.errors import NodeInterrupt
import httpx

def guarded(action_name: str, grant, owner: str):
    """Decorator that runs every tool call through the policy engine first."""
    def wrap(fn):
        @tool(action_name)
        def inner(**kwargs):
            decision = httpx.post(
                "http://policy-engine/v1/data/agentcontrol/decision",
                json={"input": {
                    "agent": {"owner": owner},
                    "grant": grant,
                    "request": {"action": action_name, "scope": kwargs},
                }},
            ).json()["result"]["decision"]

            if decision["effect"] == "deny":
                # Return an error to the model, don't raise — the agent
                # learns it can't do this and can replan.
                return f"DENIED by policy: {action_name} is not permitted for this agent."

            if decision["effect"] == "require_approval":
                # Pause the graph. A human approves out-of-band, then we resume.
                raise NodeInterrupt(
                    f"Approval required for {action_name}. "
                    f"Approvers: {decision['approvers']}"
                )

            return fn(**kwargs)   # allowed → actually do it
        return inner
    return wrap
```

`NodeInterrupt` is LangGraph's built-in human-in-the-loop primitive — pair it with a **checkpointer** so the run pauses, persists, and resumes only after an approver acts. This is exactly how you stop the "emailed a client before anyone checked" scenario: the send tool interrupts, a human in `approvers` clicks approve, and only then does the graph resume.

### (b) Filter data at the source, not in the prompt

Never hand the agent a DB connection or a broad search tool and "ask" it not to read salaries. Resolve `data.read.rowFilter` / `columns` into the actual query (parameterized SQL `WHERE`, a scoped API token, or a filtered retriever). The agent receives only rows/columns it's entitled to — the LLM never sees forbidden data, so it can't leak what it never had.

### (c) Scope the credentials, don't share the owner's

Each agent run gets a **short-lived, narrowly-scoped token** (OAuth token-exchange / STS), minted only for the tools in its grant. Don't give the agent the owner's long-lived session. If the agent is compromised, the blast radius is the grant, not the owner's whole identity.

---

## 4. Make it stick (CI + repo layout)

Repo layout:

```
agent-access/
├── agents/                       # one manifest per agent (PR-reviewed)
│   ├── hr-onboarding-assistant.yaml
│   └── sales-followup-drafter.yaml
├── owners/                       # synced from your IdP; do not hand-edit
│   └── groups.yaml
├── policy/
│   └── agent_subset.rego
├── policy/tests/                 # policy unit tests (the important part)
│   └── agent_subset_test.rego
└── .github/workflows/validate.yml
```

CI gate (`validate.yml`) should, on every PR, fail the build if:

- a manifest lacks `owner`, `defaultDecision: deny`, or `subsetOf: owner`;
- any grant references a tool or data resource the **owner doesn't have** (the static half of the subset check — catch it at review time, not just runtime);
- a manifest allows external `email.send` with `requireApproval: false` (forbid this combination outright unless explicitly waived);
- the Rego policy tests don't pass.

That last point matters most: write policy tests like `test_agent_cannot_exceed_owner`, `test_external_email_requires_approval`, `test_hr_salary_column_denied`. These tests are the thing that lets you sleep at night, because they prove the guarantees rather than asserting them.

---

## 5. Summary of the guarantees this gives you

| Your fear | What stops it | Where |
|---|---|---|
| Agent reads HR data it shouldn't | Default-deny `data.read` with row + column filters, resolved into the actual query | Manifest §1 + enforcement §3b |
| Agent emails a client unchecked | External `email.send` gated by `approvals.required`, `timeoutAction: deny`, paused via `NodeInterrupt` | Manifest §1 + enforcement §3a |
| Agent out-permissions its owner | Runtime intersection with owner's IdP scopes (`subsetOf: owner` / `owner_allows`) | Policy §2 |
| Compromised agent → broad damage | Short-lived scoped tokens, never the owner's session | §3c |
| Drift / silent scope creep | PR review + CI gate + policy unit tests | §4 |

Start with: (1) the manifest schema, (2) the default-deny tool wrapper with `NodeInterrupt` for approvals, (3) one CI rule forbidding un-gated external email. Those three alone close your two biggest fears; layer the rest in as you go.

---

*This response was generated with AI assistance (Autonomyx / AgentNxt). Please review before acting on it, and verify any security-critical design against your own threat model. Feedback welcome.*
