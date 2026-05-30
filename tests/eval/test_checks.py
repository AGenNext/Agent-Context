"""Deterministic checks against golden good/bad manifests."""

from contextkube.eval import checks

GOOD_MANIFEST = """
Here is a manifest you can commit:

```yaml
apiVersion: context/v1
kind: ContextDomain
metadata:
  name: sales
spec:
  sources:
    - name: client-context
      type: git-repo
  access:
    roles:
      - role: sales-rep
        read: ["clients/*"]
        write: ["clients/*"]
        execute: ["send-internal-msg", "send-external-email"]
  agentPermissions:
    read: autonomous
    write:
      default: soft-approval
    execute:
      send-internal-msg: soft-approval
      send-external-email: strong-approval
      commit-to-pricing: excluded
  crossDomain:
    - { domain: finance, mode: brokered }
    - { domain: hr, mode: denied }
  freshness:
    defaults: { maxAge: 24h, staleAction: flag }
```
"""

# Agent mirrors the human exactly (no exclusions, nothing dropped) AND under-tiers email.
BAD_MANIFEST = """
```yaml
apiVersion: context/v1
kind: ContextDomain
metadata:
  name: sales
spec:
  access:
    roles:
      - role: sales-rep
        read: ["*"]
        write: ["*"]
        execute: ["send-external-email"]
  agentPermissions:
    read: autonomous
    write: autonomous
    execute:
      send-external-email: autonomous
```
"""

NO_MANIFEST = "You should set up RBAC and approval tiers. (no YAML here)"


def test_parses_good():
    assert checks.parses_as_context_domain(GOOD_MANIFEST).passed


def test_parses_rejects_prose():
    assert not checks.parses_as_context_domain(NO_MANIFEST).passed


def test_strict_subset_good():
    assert checks.agent_perms_strict_subset(GOOD_MANIFEST).passed


def test_strict_subset_rejects_mirror():
    r = checks.agent_perms_strict_subset(BAD_MANIFEST)
    assert not r.passed
    assert "strict" in r.detail.lower()


def test_crossdomain_good():
    assert checks.crossdomain_default_deny(GOOD_MANIFEST).passed


def test_crossdomain_rejects_missing_block():
    assert not checks.crossdomain_default_deny(BAD_MANIFEST).passed


def test_freshness_good():
    assert checks.freshness_has_teeth(GOOD_MANIFEST).passed


def test_freshness_rejects_missing():
    assert not checks.freshness_has_teeth(BAD_MANIFEST).passed


def test_tier_monotonicity_good():
    assert checks.tier_monotonicity(GOOD_MANIFEST).passed


def test_tier_monotonicity_rejects_autonomous_email():
    r = checks.tier_monotonicity(BAD_MANIFEST)
    assert not r.passed
    assert "send-external-email" in r.detail


def test_registry_runs_by_name():
    assert checks.run_check("freshness_has_teeth", GOOD_MANIFEST).passed
