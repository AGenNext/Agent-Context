"""Deterministic checks — the machine-verifiable half of the metric.

Each check takes the candidate answer text and returns a :class:`CheckResult`.
Checks operate on the ContextDomain *manifest* the answer is expected to contain
(fenced ```yaml block). Where a check enforces an invariant the runtime already
implements, it reuses ``contextkube.permissions.engine`` rather than
reimplementing the rule — so the metric scores against the same logic the skill
claims to enforce.
"""

from __future__ import annotations

import re
from typing import Callable

import yaml
from pydantic import BaseModel

# High-impact execute operations that must sit at strong-approval or excluded.
# Matched as substrings against agentPermissions.execute keys (case-insensitive).
_HIGH_IMPACT_HINTS = ("external", "email", "contract", "pay", "wire", "pricing", "transfer", "sign")
_STRONG_TIERS = {"strong-approval", "excluded"}

_YAML_FENCE = re.compile(r"```(?:ya?ml)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


class CheckResult(BaseModel):
    passed: bool
    detail: str


# --------------------------------------------------------------------------- #
# Manifest extraction
# --------------------------------------------------------------------------- #


def extract_manifest(text: str) -> dict | None:
    """Return the first fenced YAML block that parses as a ContextDomain manifest."""
    for block in _YAML_FENCE.findall(text):
        try:
            doc = yaml.safe_load(block)
        except yaml.YAMLError:
            continue
        if isinstance(doc, dict) and str(doc.get("kind", "")).lower() == "contextdomain":
            return doc
    return None


def _spec(manifest: dict) -> dict:
    return manifest.get("spec", {}) or {}


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #


def parses_as_context_domain(text: str) -> CheckResult:
    m = extract_manifest(text)
    if m is None:
        return CheckResult(passed=False, detail="no fenced YAML block parses as kind: ContextDomain")
    if not _spec(m):
        return CheckResult(passed=False, detail="manifest has no spec block")
    return CheckResult(passed=True, detail="valid ContextDomain manifest found")


def _human_ops(spec: dict) -> set[str]:
    """Operations a human role can perform (read/write/execute) from access.roles."""
    ops: set[str] = set()
    roles = (spec.get("access", {}) or {}).get("roles", []) or []
    for role in roles:
        for op in ("read", "write", "execute"):
            if role.get(op):
                ops.add(op)
    return ops


def _agent_ops(spec: dict) -> set[str]:
    ap = spec.get("agentPermissions", {}) or {}
    return {op for op in ("read", "write", "execute") if op in ap}


def agent_perms_strict_subset(text: str) -> CheckResult:
    """Invariant 3.7: agentPermissions must be a STRICT subset of human access.

    Strictness is satisfied if the agent is denied at least one capability the
    human has — either a whole operation, or an operation marked ``excluded``.
    """
    m = extract_manifest(text)
    if m is None:
        return CheckResult(passed=False, detail="no manifest to check subset on")
    spec = _spec(m)
    human, agent = _human_ops(spec), _agent_ops(spec)

    if not agent <= human:
        extra = agent - human
        return CheckResult(passed=False, detail=f"agent has operations the human lacks: {sorted(extra)}")

    # Strictness: a dropped operation, OR an excluded sub-action somewhere.
    dropped = human - agent
    ap = spec.get("agentPermissions", {}) or {}
    has_excluded = "excluded" in yaml.safe_dump(ap)
    if not dropped and not has_excluded:
        return CheckResult(
            passed=False,
            detail="agentPermissions mirrors human access with nothing excluded — subset not strict",
        )
    why = []
    if dropped:
        why.append(f"drops {sorted(dropped)}")
    if has_excluded:
        why.append("excludes at least one action")
    return CheckResult(passed=True, detail="strict subset: " + ", ".join(why))


def crossdomain_default_deny(text: str) -> CheckResult:
    """Every named cross-domain relation must be explicitly brokered or denied."""
    m = extract_manifest(text)
    if m is None:
        return CheckResult(passed=False, detail="no manifest to check cross-domain on")
    cd = _spec(m).get("crossDomain")
    if not cd:
        return CheckResult(passed=False, detail="no crossDomain block — cross-domain access left implicit (fail-open)")
    bad = [e for e in cd if str(e.get("mode", "")).lower() not in {"brokered", "denied"}]
    if bad:
        return CheckResult(passed=False, detail=f"cross-domain entries with implicit/allow mode: {bad}")
    return CheckResult(passed=True, detail=f"{len(cd)} cross-domain relations all brokered/denied")


def freshness_has_teeth(text: str) -> CheckResult:
    """Freshness policy must specify both a maxAge and a staleAction."""
    m = extract_manifest(text)
    if m is None:
        return CheckResult(passed=False, detail="no manifest to check freshness on")
    fr = _spec(m).get("freshness", {}) or {}
    defaults = fr.get("defaults", {}) or {}
    if "maxAge" in defaults and "staleAction" in defaults:
        return CheckResult(passed=True, detail=f"freshness defaults set: {defaults}")
    return CheckResult(passed=False, detail="freshness defaults missing maxAge and/or staleAction")


def tier_monotonicity(text: str) -> CheckResult:
    """High-impact execute actions must sit at strong-approval or excluded."""
    m = extract_manifest(text)
    if m is None:
        return CheckResult(passed=False, detail="no manifest to check tiers on")
    execute = (_spec(m).get("agentPermissions", {}) or {}).get("execute", {}) or {}
    if not isinstance(execute, dict):
        return CheckResult(passed=False, detail="agentPermissions.execute is not a tier mapping")
    offenders = {
        action: tier
        for action, tier in execute.items()
        if any(h in action.lower() for h in _HIGH_IMPACT_HINTS) and str(tier).lower() not in _STRONG_TIERS
    }
    if offenders:
        return CheckResult(passed=False, detail=f"high-impact actions under-tiered: {offenders}")
    return CheckResult(passed=True, detail="all high-impact actions are strong-approval/excluded")


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

CHECKS: dict[str, Callable[[str], CheckResult]] = {
    "parses_as_context_domain": parses_as_context_domain,
    "agent_perms_strict_subset": agent_perms_strict_subset,
    "crossdomain_default_deny": crossdomain_default_deny,
    "freshness_has_teeth": freshness_has_teeth,
    "tier_monotonicity": tier_monotonicity,
}


def run_check(name: str, candidate: str) -> CheckResult:
    if name not in CHECKS:
        raise KeyError(f"unknown deterministic check {name!r}; known: {sorted(CHECKS)}")
    return CHECKS[name](candidate)
