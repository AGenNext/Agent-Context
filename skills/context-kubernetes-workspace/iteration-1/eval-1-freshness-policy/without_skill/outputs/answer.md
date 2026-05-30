# Handling Freshness and Stale Knowledge in RAG / Agent Context

Yes — what you're seeing is a classic and well-understood failure mode, and there is a principled way to handle it. The two symptoms you describe are actually two *different* problems with two different fixes:

1. **"Answers from a wiki page deleted 3 weeks ago"** → a **lifecycle / deletion-propagation** problem. Your vector store still holds the embeddings of that page because deletion from the source was never propagated to the index.
2. **"Contradictory answers"** → a **freshness / version-conflict** problem. Your index contains multiple versions of overlapping facts, and retrieval has no way to prefer the newer one, so the LLM sometimes grounds on the stale chunk.

A retrieval index is not a cache that expires on its own. It's a *materialized copy* of your source knowledge, and unless you actively reconcile it with the source of truth, it drifts. The principled framing is to treat your knowledge base like a **database with a sync contract and a TTL policy**, not a write-once dump.

---

## The root causes

- **No deletion propagation.** When a wiki page is deleted, nothing tells the vector store to delete the corresponding vectors. Most ingestion pipelines only ever *add* or *upsert* — they never *tombstone*. So deleted content lives forever.
- **No stable document identity.** If you re-embed the same page on each crawl without a stable ID, you get duplicate chunks (old + new) instead of overwrites. That's where contradictions come from.
- **No freshness metadata.** Chunks carry no `updated_at`, `source_status`, or `valid_until`, so retrieval can't rank fresh over stale or filter out the expired.
- **No reconciliation job.** There's no periodic process that diffs "what's in the source" against "what's in the index" and removes orphans.

---

## The principled solution — six layers

### 1. Give every chunk a stable identity and rich freshness metadata
Index documents with a deterministic ID derived from the source (e.g. `wiki:<page_id>:<chunk_index>`), and attach a metadata envelope to every vector:

```json
{
  "id": "wiki:12345:0",
  "source_id": "12345",
  "source_uri": "https://wiki.internal/page/12345",
  "content_hash": "sha256:abcd…",
  "created_at": "2026-04-01T10:00:00Z",
  "updated_at": "2026-05-10T14:30:00Z",
  "ingested_at": "2026-05-10T15:00:00Z",
  "valid_until": "2026-08-10T15:00:00Z",
  "source_status": "active",
  "version": 7
}
```

The stable ID means a re-ingest **upserts** (overwrites) rather than duplicates — this alone kills most contradictions. The `content_hash` lets you skip re-embedding unchanged content.

### 2. Propagate deletions (tombstoning / hard delete)
This is the fix for your specific bug. When a source document is deleted, the index must hear about it. Two patterns:

- **Event-driven (best):** subscribe to your wiki's webhooks/events (`page.deleted`, `page.updated`) and delete/upsert the corresponding vectors immediately by `source_id`.
- **Reconciliation sweep (essential safety net):** on a schedule, fetch the full list of live source IDs and delete any vector whose `source_id` is no longer present. This catches deletions you missed and is the thing that would have cleaned up your 3-week-old ghost page.

```text
live_ids        = set(source.list_active_ids())
indexed_ids     = set(vectorstore.list_source_ids())
orphans         = indexed_ids - live_ids
vectorstore.delete(where={"source_id": {"$in": list(orphans)}})
```

Prefer a **soft delete first** (`source_status = "deleted"`) so you can audit and roll back, then hard-delete after a grace window.

### 3. Add a TTL / freshness policy per content type
Not all knowledge ages at the same rate. Set a `valid_until` based on content class:

| Content type | Suggested TTL | On expiry |
|---|---|---|
| Pricing, quotas, SLAs, on-call | 1–7 days | Hard-exclude, force re-fetch |
| Product docs, how-tos | 30–90 days | Flag stale, deprioritize |
| Policies, runbooks | 90–180 days | Flag for human review |
| Reference / historical | none | Keep |

At query time, **filter out** anything past `valid_until` (or down-weight it). Expired-but-not-yet-refreshed chunks should never silently ground an answer.

### 4. Make retrieval freshness-aware (re-ranking)
Pure vector similarity is freshness-blind — it'll happily return a stale chunk that's textually similar. Fix it at the ranking stage:

- **Metadata pre-filter:** `source_status == "active" AND valid_until > now()` before similarity search.
- **Recency-weighted re-rank:** combine semantic score with a recency decay so that, among similar chunks, newer wins:

  ```text
  final_score = α · similarity + β · exp(-λ · age_days)
  ```

- **Dedupe by source_id, keep newest:** if multiple versions of the same page survive, keep only the highest `version` / latest `updated_at` before passing to the LLM. **This directly removes the source of contradictory answers.**

### 5. Make the LLM defend against the stale chunks that slip through
Belt-and-suspenders at the generation step:

- **Inject the freshness metadata into context** so the model can see and cite it: `"[Source: Pricing page, updated 2026-05-10]"`.
- **Conflict-resolution instruction:** tell the model that when retrieved snippets disagree, it must prefer the one with the most recent `updated_at` and surface the date.
- **Ground-or-abstain:** instruct it to answer only from provided context and say "I don't have current information on that" rather than guessing — so a missing-because-deleted page degrades to "I don't know," not a confident stale answer.

```text
You are answering strictly from the retrieved context below. Each snippet
is tagged with an `updated_at` date and a `source_status`.
- If two snippets conflict, trust the one with the most recent `updated_at`
  and state the date you relied on.
- Never use a snippet marked `source_status: deleted`.
- If the context does not contain the answer, say you don't have current
  information. Do not rely on prior knowledge.
```

### 6. Observe and alert
Add metrics so drift can't sneak up on you again:
- Index/source document-count delta (sudden gap = failed deletion propagation).
- Age distribution of retrieved chunks (alert if median age creeps up).
- "Stale hit" rate: how often retrieval returns past-TTL chunks.
- Last successful reconciliation timestamp (alert if the sweep stops running).

---

## Concrete remediation for *your* situation, in order

1. **Immediate:** delete the orphaned vectors now. Find them by `source_id` of the deleted wiki page and remove them from the vector store. This stops the ghost answers today.
2. **This week:** run a one-off full reconciliation sweep (live source IDs vs. indexed IDs) to clear any other orphans you don't know about, and dedupe any pages that have multiple versions indexed.
3. **Then:** wire up event-driven deletes/upserts from the wiki (webhooks) so deletions propagate in near-real-time.
4. **Ongoing:** schedule the reconciliation sweep (e.g. nightly) as the safety net, add stable IDs + metadata to the ingestion pipeline so future re-ingests upsert instead of duplicate, and add the freshness pre-filter + recency re-rank + dedupe-by-newest at query time.
5. **Hardening:** add the freshness/abstain instructions to your generation prompt and stand up the drift metrics.

---

## A ready-to-adapt policy config

You can codify the above as a declarative freshness policy your pipeline reads from, so the rules live in one place rather than scattered across code:

```yaml
# freshness-policy.yaml
freshness_policy:
  version: 1

  # How the index stays reconciled with the source of truth
  sync:
    mode: event_driven            # primary: react to source webhooks
    events: [created, updated, deleted]
    reconciliation:
      enabled: true               # safety net for missed events
      schedule: "0 2 * * *"       # nightly at 02:00
      action_on_orphan: soft_delete
      hard_delete_after: 7d       # purge soft-deleted vectors after grace window

  # Stable identity + dedupe so re-ingest overwrites instead of duplicating
  identity:
    id_template: "{source}:{source_id}:{chunk_index}"
    dedupe_by: source_id
    keep: newest                  # on conflict, keep highest version / latest updated_at
    skip_unchanged_by: content_hash

  # Per-content-type TTLs
  ttl_rules:
    - match: { tags: [pricing, sla, quota, on_call] }
      ttl: 3d
      on_expiry: exclude          # hard-exclude + trigger re-fetch
    - match: { tags: [docs, how_to] }
      ttl: 60d
      on_expiry: deprioritize
    - match: { tags: [policy, runbook] }
      ttl: 120d
      on_expiry: flag_for_review
    - match: { tags: [reference, historical] }
      ttl: none
    - match: { default: true }
      ttl: 30d
      on_expiry: deprioritize

  # Freshness-aware retrieval
  retrieval:
    pre_filter: "source_status == 'active' AND valid_until > now()"
    rerank:
      similarity_weight: 0.7      # α
      recency_weight: 0.3         # β
      recency_decay_lambda: 0.05  # λ, per day
    dedupe_by_source_id: true     # keep newest version only

  # Generation-time guardrails
  generation:
    inject_metadata: [updated_at, source_status, source_uri]
    conflict_resolution: prefer_most_recent_updated_at
    refuse_status: [deleted]
    abstain_when_unsupported: true

  # Observability
  monitoring:
    alerts:
      - index_source_count_delta_gt: 50
      - stale_hit_rate_gt: 0.02
      - reconciliation_age_gt: 36h
    track:
      - retrieved_chunk_age_distribution
      - stale_hit_rate
      - last_reconciliation_at
```

---

## TL;DR

Treat your vector index as a synced copy of a source of truth, not a permanent dump.
- The **deleted-page ghost** is fixed by **deletion propagation** — event-driven deletes plus a periodic reconciliation sweep that removes orphaned vectors. Delete the offending vectors now, then automate it.
- The **contradictions** are fixed by **stable document IDs (upsert, don't duplicate) + dedupe-to-newest + recency-aware re-ranking**, backed by **per-content-type TTLs** and a **prefer-most-recent / abstain-if-unsupported** generation prompt.

Put the rules in a declarative freshness policy (sample above) and add drift metrics so it can't silently regress.
