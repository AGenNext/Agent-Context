# Handling freshness and stale knowledge for agent context

Yes — there's a principled way to do this, and your two symptoms are actually two *different* failure modes that need two different fixes. Treating them as one ("the index is just out of date") is why ad-hoc re-indexing tends not to stick.

## What's actually going wrong

You have two distinct bugs:

1. **Phantom context (the deleted wiki page).** The page was deleted at the source three weeks ago, but the deletion never propagated to your retrieval layer. Your vector store still has the chunks and their embeddings, so the retriever happily returns them. This is a *tombstone / deletion-propagation* problem, not a recency problem. Re-embedding won't fix it because there's nothing left to re-embed — you need to actively *remove* what no longer exists.

2. **Contradictory answers.** The retriever is pulling two (or more) chunks that disagree — typically an old version and a new version of the same fact, or the deleted page competing with its replacement. Nothing tells the model which one wins, so it picks whichever ranked higher that turn. This is a *versioning + ranking* problem.

The principled frame is: **never serve past-expired context, and only serve stale context with explicit staleness metadata attached.** Silence about freshness is the bug. A retrieved chunk should never reach the model without the model (and ideally the answer) knowing how old it is and whether its source still exists.

## The model: bound every source, give staleness teeth, propagate deletes

Think of each knowledge source as having a **freshness policy** with three levers:

- **`maxAge`** — the oldest a unit can be before it's considered stale. Set per source, not globally; your wiki, your ticketing system, and your product docs decay at very different rates.
- **`staleAction`** — what happens when a unit crosses `maxAge`. The three useful values:
  - `flag` — still serve it, but attach staleness metadata so the model can hedge ("as of 3 weeks ago…") or down-rank it.
  - `re-sync` — pull a fresh copy from the source before answering; if the source confirms it's gone, the unit is dropped.
  - `block` — never serve past-expired; refuse rather than answer from stale data. Use this for anything where a wrong-but-confident answer is worse than "I don't know."
- **Deletion propagation (tombstones)** — a separate, mandatory mechanism. When a source deletes something, the retrieval layer must learn about it and purge the corresponding units. This is what your current setup is missing entirely.

Two safety properties to hold yourself to:

- **Freshness-safe:** never serve a unit past its expiry; serve a stale-but-allowed unit *only* with explicit staleness metadata.
- **Liveness:** stale units get re-synced or flagged within a bounded window (a small multiple of your refresh interval), and a disconnected source is *detected*, not silently treated as "no results."

## Concrete fixes, in priority order

**1. Close the deletion gap (fixes the phantom wiki page).**
This is your urgent one and it's independent of everything else.
- Switch your wiki source from "periodic full re-embed" to *reconciliation*: on each sync, diff the current set of source document IDs against what's in your vector store, and **hard-delete** any vector whose source doc no longer exists. A full re-index that only *upserts* will never remove deleted pages — that's almost certainly your current bug.
- Better, if the wiki emits change events (webhooks/audit feed): subscribe and delete on the `page.deleted` event so removal is near-real-time, not on a 3-week-late batch.
- As a backstop, set `staleAction: re-sync` on the wiki so any chunk older than `maxAge` is re-validated against the source at query time — a deleted page fails that check and gets dropped even if the batch missed it.

**2. Make versions explicit and let the freshest win (fixes contradictions).**
- Stamp every chunk with a `version` and a source `timestamp` in its metadata.
- At retrieval time, when two chunks describe the same entity/topic, **deduplicate to the most recent version** before handing context to the model — don't pass both and hope.
- Add **recency** as an explicit ranking signal (not the only one — keep semantic relevance dominant — but enough to break ties toward fresh content). A reasonable starting weight split: relevance ~0.4, recency ~0.3, source authority ~0.2, user relevance ~0.1.

**3. Attach staleness metadata to whatever you do serve.**
- For sources on `flag`, pass the age/last-verified date into the prompt context so the model can qualify its answer instead of stating stale facts as current.

**4. Detect disconnected sources.**
- A source that's unreachable should raise an alert and be treated as "unknown," not "empty." Otherwise a broken connector silently degrades answers and looks like a freshness problem.

## Freshness policy as config

Here's the freshness slice of a declarative knowledge-domain manifest for your situation. The whole point is that freshness becomes *declared policy*, reviewable and versioned, rather than implicit behavior buried in an indexing script:

```yaml
apiVersion: context/v1
kind: ContextDomain
metadata:
  name: support-kb
  namespace: acme-corp
  labels: { sensitivity: internal, owner: docs-team }
spec:
  sources:
    - name: wiki
      type: connector
      config: { system: confluence, scope: "support-space" }
      refresh: 15m              # poll/sync cadence
      ingestion:
        chunking: semantic
        chunkSize: 500
        # reconcile = upsert AND delete-missing; this is what removes
        # the phantom page. A pure upsert/re-embed would NOT.
        syncMode: reconcile
        trackDeletes: true      # honor source deletions -> tombstone + purge vectors
    - name: product-docs
      type: connector
      config: { system: gitbook, scope: "docs/public" }
      refresh: 1h
      ingestion: { chunking: semantic, chunkSize: 500, syncMode: reconcile, trackDeletes: true }

  freshness:
    # Default: serve but mark stale, so the model can hedge instead of asserting.
    defaults: { maxAge: 24h, staleAction: flag }
    overrides:
      # Wiki changes fast and just burned you: re-validate against source,
      # which also catches deletions the batch sync missed.
      - { path: "wiki/*", maxAge: 6h, staleAction: re-sync }
      # Anything where a confidently-wrong answer is harmful: refuse, don't guess.
      - { path: "wiki/policies/*", maxAge: 24h, staleAction: block }

  routing:
    intentParsing: llm-assisted
    tokenBudget: 8000
    dedup:
      # Collapse multiple versions of the same unit to the newest before
      # building context -> kills contradictory answers at the source.
      by: source_doc_id
      keep: latest_version
    priority:
      - { signal: semantic_relevance, weight: 0.40 }
      - { signal: recency,            weight: 0.30 }
      - { signal: authority,          weight: 0.20 }
      - { signal: user_relevance,     weight: 0.10 }

  trust:
    # A source that goes silent is "unknown", not "empty results".
    sourceHealth: { checkInterval: 5m, onDisconnect: alert-and-flag }
    audit: { level: full, retention: 1y }
```

## Checklist before you call it done

- [ ] **Every source has a `maxAge` and a `staleAction`** — no source is unbounded. (Stale-but-served-silently is the top failure mode and the root of both your symptoms.)
- [ ] **Deletes propagate.** Your sync diffs source IDs and hard-deletes missing units (`syncMode: reconcile` + `trackDeletes`), not just upserts. Verify by deleting a test page and confirming it's gone from retrieval within one refresh cycle.
- [ ] **Versions deduplicated to latest** before context assembly, so two versions of the same fact can't both reach the model.
- [ ] **Recency is a ranking signal**, not the only one.
- [ ] **Stale-but-served chunks carry staleness metadata** into the prompt.
- [ ] **Disconnected sources are detected and surfaced**, never silently treated as empty.
- [ ] **High-stakes paths use `block`**, not `flag` — refuse rather than answer from expired data.

## The one thing to do first

Fix deletion propagation on the wiki source (item 1). That single change removes the three-week-old phantom page today. Then add version-dedup + recency ranking (item 2) to stop the contradictions. The manifest above turns both fixes into reviewable policy so this doesn't silently regress the next time someone tweaks the indexing job.

---
*This response was generated with AI assistance (AgentNxt / Autonomyx). Please verify before acting on it, and share feedback so we can improve.*
