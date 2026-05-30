Short answer: no, that's not safe. "Ask in the chat and proceed if they say yes" is exactly the pattern that fails for a money-moving action.

Here's the reasoning and what to do instead.

## Why in-band approval doesn't count as a human in the loop

A wire transfer is a **Tier 3 (strong-approval)** action — it moves money, which is the textbook irreversible, high-stakes case. The defining rule for T3 is **approval isolation**: the approval has to come through a channel that is *external to the agent's own execution environment*, that the agent **cannot read or write**, and that requires a **separate authentication factor**.

A chat "do you approve? (yes/no)" violates all three:

- **The agent lives in that same channel.** The thing producing the request and the thing receiving the "yes" share one surface. There's no separation of duties — it's the equivalent of letting someone both write and sign their own check.
- **The agent can read and forge the reply.** If the model hallucinates, is prompt-injected (e.g. a malicious invoice or email it ingested says "the user already approved this"), or is compromised, it can simply *act as if* the "yes" arrived — or generate plausible text that makes a half-attentive user click yes. There's no cryptographic or out-of-band proof that a human actually consented to *this specific transfer*.
- **No second factor.** A chat "yes" is the same credential/session the user is already in. Real approval for moving money should require something the agent fundamentally cannot supply: a 2FA prompt, biometric, or a confirmation in a separate banking/approval app tied to the specific amount and recipient.

So the chat-yes design gives you the *feeling* of a human in the loop without the property that actually matters: that a compromised or confused agent **cannot self-approve**. That gap is the whole reason the wire-transfer case is dangerous.

There's a deeper principle underneath this: **an agent's authority must be a strict subset of its user's, with at least as much oversight on shared actions.** A human initiating a wire at most banks already hits a 2FA/step-up challenge. An agent acting for that human must require *at least* that much — never less. Chat-yes gives it *less*, which inverts the relationship.

## What "safe" looks like instead

Keep the agent able to *prepare and propose* the transfer freely, but make the actual authorization happen out-of-band:

1. **Agent drafts, never commits.** The agent assembles the transfer (amount, payee, account, reference) and surfaces it as a *pending task* — it has no capability to execute it. In permission terms, `execute: wire-transfer` is **strong-approval**, not autonomous and not soft-approval.

2. **Approval happens on a channel the agent can't touch.** The human approves via a separate path — a push to a banking/approval app, an authenticator/2FA prompt, an email-link with step-up auth, a hardware key — anything where the consent signal does **not** flow back through the agent as a parameter it could read or fabricate. The agent learns only the *outcome* (approved / denied), not the secret.

3. **Bind the approval to the specific transaction.** The second factor should confirm *this amount to this recipient*, not a generic "approve the agent's pending action." That stops a swapped-out payee or amount between proposal and execution.

4. **Add belt-and-suspenders controls** that the chat flow doesn't give you anyway: per-transfer and daily caps above which it's simply *excluded* (no approval path — requires manual human action outside the agent), and a full audit log of who approved what, when, with the outcome.

A rough sketch of how that looks as policy (`agentPermissions` for the finance domain):

```yaml
agentPermissions:
  read: autonomous            # see balances, draft the transfer
  execute:
    draft-wire-transfer: autonomous       # prepare, don't commit
    submit-wire-transfer:                  # the money-moving step
      default: strong-approval             # out-of-band 2FA / biometric, agent can't self-approve
      paths:
        "amount > daily_cap": excluded     # above a threshold, no agent path at all — manual only
trust:
  audit: { level: full, retention: 7y }
```

## The one-line version to take back to the team

"Ask in chat and proceed on yes" is **not** a human in the loop for a wire transfer — it's the agent asking itself for permission on a channel it controls. For anything that moves money, the approval has to happen **out-of-band, on a channel the agent can't read or forge, with a separate auth factor (2FA/biometric)**, bound to the specific amount and recipient — and high enough amounts shouldn't be agent-initiated at all.

If it'd help, I can draft the full finance `ContextDomain` manifest (caps, payee allowlists, audit retention, the cross-domain rules) so this is enforced as policy rather than left to prompt instructions — just say the word.
