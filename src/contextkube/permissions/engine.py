"""Permission Engine — three-tier agent permission model (§3.4).

Enforces two design invariants from the paper:

  Invariant 3.7 (Agent Permission Subset):  P_au ⊂ P_u  (strict)
      For every shared operation o ∈ P_au:  T(o, agent) ≥ T(o, user).

  Invariant 3.8 (Strong Approval Isolation): any Tier-3 action is approved on a
      channel external to, and not readable/writable by, the agent, requiring a
      separate authentication factor.

The engine is *fail-closed*: any access it cannot positively authorize is
denied (Design Goal 3.9).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from contextkube.core.models import (
    AgentProfile,
    ContextUnit,
    Operation,
    PermissionTier,
)


# Tier ordering: more oversight = higher rank. Used to evaluate T(o,a) ≥ T(o,u).
_TIER_RANK: dict[PermissionTier, int] = {
    PermissionTier.T1_AUTONOMOUS: 0,
    PermissionTier.T2_SOFT_APPROVAL: 1,
    PermissionTier.T3_STRONG_APPROVAL: 2,
    PermissionTier.EXCLUDED: 3,  # highest = "never, manual only"
}


def tier_rank(tier: PermissionTier) -> int:
    """Rank a tier so that invariants reduce to integer comparisons."""
    return _TIER_RANK[tier]


class UserPermissions(BaseModel):
    """P_u — what a *human* user is authorized to do.

    ``capabilities`` is the set of operations the user can perform (the support
    of P_u). This is the ceiling the agent's profile must stay strictly under.
    """

    role: str
    capabilities: set[Operation] = Field(default_factory=set)


class AccessDecision(BaseModel):
    """Outcome of an access check, with the tier of oversight it requires."""

    allowed: bool
    required_tier: PermissionTier | None = None
    reason: str


class PermissionEngine:
    """Computes and enforces the agent permission model."""

    # ----- Invariant 3.7 verification -------------------------------------

    def verify_subset(self, user: UserPermissions, agent: AgentProfile) -> bool:
        """Return True iff P_au ⊂ P_u holds *strictly* (Invariant 3.7).

        Conditions:
          1. Every operation the agent has a tier for is one the user can do.
          2. The subset is strict: the user can do at least one op the agent
             cannot (i.e. the agent is not granted every user capability).
          3. For each shared op, T(o, agent) ≥ T(o, user). Here the user's
             baseline tier is autonomous (humans act with their own authority),
             so any agent tier satisfies this; the check guards against an
             agent being assigned a *lower* tier than a policy floor.
        """
        agent_ops = set(agent.tiers.keys())
        if not agent_ops <= user.capabilities:          # condition 1
            return False
        if not agent_ops < user.capabilities:            # condition 2 (strict)
            return False
        return True

    # ----- Access check (fail-closed) -------------------------------------

    def check_access(
        self,
        unit: ContextUnit,
        agent: AgentProfile,
        operation: Operation,
    ) -> AccessDecision:
        """Authorize ``operation`` by ``agent`` on ``unit`` — fail-closed.

        Denies unless ALL hold: the unit's scope π authorizes the agent's role,
        and the agent has a (non-excluded) tier for the operation.
        """
        if not unit.authorizes(agent.role):
            return AccessDecision(
                allowed=False,
                reason=f"role {agent.role!r} not in unit scope π",
            )
        tier = agent.tiers.get(operation)
        if tier is None or tier is PermissionTier.EXCLUDED:
            return AccessDecision(
                allowed=False,
                reason=f"operation {operation.value!r} excluded for agent",
            )
        return AccessDecision(
            allowed=True,
            required_tier=tier,
            reason="authorized",
        )


# ---------------------------------------------------------------------------
# USER CONTRIBUTION — the permission projection (Design Invariant 3.7)
# ---------------------------------------------------------------------------


def project_agent_permissions(
    user: UserPermissions,
    excluded_ops: set[Operation],
    tier_overrides: dict[Operation, PermissionTier] | None = None,
) -> AgentProfile:
    """Derive an agent's profile (α) as a STRICT subset of its user's authority.

    This is the heart of the model: given what a human can do (``user``), decide
    what the agent acting on their behalf may do, and at what oversight tier.

    TODO(you): implement the projection. It must produce an AgentProfile whose
    ``tiers`` keys are a strict subset of ``user.capabilities`` (so that
    PermissionEngine.verify_subset returns True). Design decisions that matter:

      * Which operations carry over? (Hint: user.capabilities minus excluded_ops
        — but you must guarantee at least one capability is dropped so the subset
        stays STRICT even when excluded_ops is empty.)
      * What default tier does each carried operation get if not in
        ``tier_overrides``? (e.g. READ→autonomous, WRITE→soft, EXECUTE→strong —
        a "trust ladder" where more impactful ops demand more oversight.)
      * How do you handle a conflict where an override would EXCLUDE an op?

    Return an AgentProfile(role=user.role, tiers={op: tier, ...}).
    """
    raise NotImplementedError("project_agent_permissions: see TODO above")
