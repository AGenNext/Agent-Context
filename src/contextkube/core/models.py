"""Core abstractions of Context Kubernetes (§3.2 of Mouzouni, 2026).

This module encodes the six foundational abstractions directly from their
formal definitions. The field names deliberately mirror the paper's tuples so
the spec doubles as the documentation:

    Context Unit       u = (c, τ, m, v, e, π)        Def. 3.1
    Context Domain     D = (N, S, A, F, ρ, O, G)     Def. 3.2
    Context Store      s = (σ, ι, φ)                 Def. 3.3
    Context Endpoint   ε(q, ω, α) → {u_1, ..., u_k}  Def. 3.4
    Context Runtime    CxRI: 6 ops per connector     Def. 3.5
    Context Operator   O = (K, L, I, Γ)              Def. 3.6
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Iterator, Protocol

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations (the closed vocabularies referenced by the definitions)
# ---------------------------------------------------------------------------


class ContextType(str, Enum):
    """τ ∈ {unstructured, structured, hybrid} — Def. 3.1."""

    UNSTRUCTURED = "unstructured"
    STRUCTURED = "structured"
    HYBRID = "hybrid"


class Operation(str, Enum):
    """The Ops set referenced by the access-control function A — Def. 3.2."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


class PermissionTier(str, Enum):
    """Three-tier agent approval model — Table 2 (§3.4).

    Authority is graduated: an operation is permitted only with at least the
    human oversight its tier demands. ``EXCLUDED`` means the agent can never
    request it (manual-only).
    """

    T1_AUTONOMOUS = "autonomous"          # acts freely, no approval
    T2_SOFT_APPROVAL = "soft-approval"    # proposes; user confirms in agent UI
    T3_STRONG_APPROVAL = "strong-approval"  # out-of-band 2FA / biometric
    EXCLUDED = "excluded"                 # cannot request at all


class FreshnessState(str, Enum):
    """The four states tracked by the Freshness Manager (§3.3)."""

    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
    CONFLICTED = "conflicted"


class StoreType(str, Enum):
    """σ — the kind of backing system a Context Store wraps (Def. 3.3)."""

    GIT_REPO = "git-repo"
    DATABASE = "database"
    CONNECTOR = "connector"
    FILESYSTEM = "filesystem"


# ---------------------------------------------------------------------------
# Def. 3.1 — Context Unit:  u = (c, τ, m, v, e, π)
# ---------------------------------------------------------------------------


class ContextMetadata(BaseModel):
    """m — the metadata set carried by every context unit (Def. 3.1)."""

    author: str | None = None
    timestamp: datetime | None = None
    domain: str | None = None
    sensitivity: str | None = None
    entities: list[str] = Field(default_factory=list)
    source: str | None = None


class ContextUnit(BaseModel):
    """u = (c, τ, m, v, e, π) — the smallest addressable element of knowledge.

    Access scope ``π`` lives on the unit itself (not in a side ACL table), so a
    permission check is a local set-membership test ``role ∈ pi`` — the property
    that makes fail-closed routing cheap and verifiable.
    """

    content: str                                  # c
    type: ContextType                             # τ
    metadata: ContextMetadata                     # m
    version: str                                  # v ∈ V
    embedding: list[float] | None = None          # e ∈ R^d
    pi: set[str] = Field(default_factory=set)     # π ⊆ R (authorized roles)

    def authorizes(self, role: str) -> bool:
        """role(α) ∈ π — the unit-local authorization predicate."""
        return role in self.pi


# ---------------------------------------------------------------------------
# Def. 3.5 — Context Runtime Interface (CxRI): the 6-op connector contract
# ---------------------------------------------------------------------------


class Connection(BaseModel):
    """Opaque handle returned by ``connect(φ)``."""

    store_id: str
    handle: Any = None


class Status(BaseModel):
    """Result of ``health(conn)``."""

    healthy: bool
    detail: str | None = None


class WriteResult(BaseModel):
    """Result of ``write(conn, path, c)``."""

    ok: bool
    version: str | None = None
    detail: str | None = None


class CxRI(ABC):
    """Standard adapter between the orchestration layer and a context store.

    Every connector implements exactly these six operations (Def. 3.5). This
    decouples the orchestrator from any specific data source — the direct
    analogue of Kubernetes' Container Runtime Interface (CRI).
    """

    @abstractmethod
    def connect(self, phi: dict[str, Any]) -> Connection: ...

    @abstractmethod
    def query(self, conn: Connection, q: str) -> list[ContextUnit]: ...

    @abstractmethod
    def read(self, conn: Connection, path: str) -> ContextUnit: ...

    @abstractmethod
    def write(self, conn: Connection, path: str, content: str) -> WriteResult: ...

    @abstractmethod
    def subscribe(self, conn: Connection, path: str) -> Iterator[ContextUnit]: ...

    @abstractmethod
    def health(self, conn: Connection) -> Status: ...


# ---------------------------------------------------------------------------
# Def. 3.3 — Context Store:  s = (σ, ι, φ)
# ---------------------------------------------------------------------------


class ContextStore(BaseModel):
    """s = (σ, ι, φ) — a backing system persisting context units.

    Stores are reached *exclusively* through the CxRI; nothing in the
    orchestration layer talks to ``phi`` directly.
    """

    name: str
    sigma: StoreType                              # σ — store type
    iota: dict[str, Any] = Field(default_factory=dict)  # ι — ingestion config
    phi: dict[str, Any] = Field(default_factory=dict)   # φ — connection spec


# ---------------------------------------------------------------------------
# Def. 3.6 — Context Operator:  O = (K, L, I, Γ)
# ---------------------------------------------------------------------------


class ContextOperator(BaseModel):
    """O = (K, L, I, Γ) — a domain-specific autonomous controller (Def. 3.6).

    Inspired by Kubernetes Operators: extends the base scheduler with
    domain-specific intelligence. ``intelligence`` is gated by a minimum signal
    threshold (θ ≥ 3) to prevent premature pattern recognition (§3.2).
    """

    knowledge_store: dict[str, Any] = Field(default_factory=dict)  # K
    reasoning_engine: dict[str, Any] = Field(default_factory=dict)  # L
    intelligence: dict[str, Any] = Field(default_factory=dict)      # I
    guardrails: list[str] = Field(default_factory=list)             # Γ


# ---------------------------------------------------------------------------
# Def. 3.2 — Context Domain:  D = (N, S, A, F, ρ, O, G)
# ---------------------------------------------------------------------------


class ContextDomain(BaseModel):
    """D = (N, S, A, F, ρ, O, G) — an isolation boundary for knowledge.

    A query in domain D_i has *no* visibility into D_j unless explicitly
    brokered through D_j's operator with the requester's permissions
    propagated (Def. 3.2). ``access`` models A: R → 2^(Ops × Tier).
    """

    name: str                                                      # N — domain id
    sources: list[ContextStore] = Field(default_factory=list)      # S
    # A: role → {(operation, required tier)}
    access: dict[str, list[tuple[Operation, PermissionTier]]] = Field(default_factory=dict)
    freshness: dict[str, Any] = Field(default_factory=dict)        # F — freshness policy
    routing: dict[str, Any] = Field(default_factory=dict)          # ρ — routing config
    operator: ContextOperator | None = None                        # O
    guardrails: list[str] = Field(default_factory=list)            # G


# ---------------------------------------------------------------------------
# Def. 3.4 — Context Endpoint:  ε(q, ω, α) → {u_1, ..., u_k} ⊆ U
# ---------------------------------------------------------------------------


class AgentProfile(BaseModel):
    """α — the agent permission profile presented to an endpoint.

    Per Design Invariant 3.7 the agent's authority is a *strict subset* of its
    user's; this profile carries the role the agent acts under plus its
    per-operation tier ceiling.
    """

    role: str
    tiers: dict[Operation, PermissionTier] = Field(default_factory=dict)


class ContextEndpoint(Protocol):
    """ε(q, ω, α) → {u_1, ..., u_k} — a stable, intent-based access interface.

    The agent never specifies *where* knowledge lives, only *what* it needs.
    The returned set must satisfy, for every unit u_i:
        π(u_i) ∋ role(α)   ∧   fresh(u_i)   ∧   Σ|u_i| ≤ B  (token budget)
    """

    def resolve(self, q: str, omega: dict[str, Any], alpha: AgentProfile) -> list[ContextUnit]:
        ...
