---
name: fine-grained-entity-typing
description: >-
  Assign fine-grained, context-sensitive types to entity mentions in text —
  walking a tree-structured type hierarchy top-down and emitting a type-path
  (e.g. person → artist → actor) per mention, using each mention's sentence to
  decide. Use this skill whenever the user wants to type, tag, classify, or
  label entities/mentions with types richer than coarse PERSON/ORG/LOC: tasks
  described as "fine-grained NER", "fine-grained entity typing", "entity
  typing", "FIGER/OntoNotes/Freebase types", mapping mentions onto a supplied
  type hierarchy or ontology, building typed training data or argument-type
  features for relation/event extraction, or resolving the same surface name to
  different types across different sentences ("Amazon" the company vs the
  river). Use it even when the user just says "NER" but clearly wants more than
  the standard 4–7 coarse classes, asks "what kind/type of entity is X in this
  sentence", or hands you a list of fine types to assign. Do NOT use it for
  entity linking/disambiguation to Wikipedia/KB IDs, plain coarse NER, PII
  redaction, dependency parsing, or entity frequency counting — those are
  different tasks even though they also involve entities.
---

# Fine-Grained Entity Typing

Assign each entity mention a **type-path** through a tree-structured hierarchy,
using the mention's **local context** to decide — not just what the entity
"usually" is. This is the task defined by AFET (Ren et al., EMNLP 2016); this
skill keeps AFET's task definition and output contract, and uses your own
reasoning in place of its learned embedding classifier.

## The core idea: context decides the type

The same surface string is different types in different sentences. This is the
whole point — never type a mention from world knowledge alone.

- *"Governor **Schwarzenegger** gives a speech on Veterans Day"* → `person → politician`
- *"action-movie star **Schwarzenegger** returns to the franchise"* → `person → artist → actor`
- *"**Schwarzenegger**'s first property investment was six units"* → `person → businessman`

A knowledge base would assign all three type sets to all three sentences — that
is the "noisy label" problem AFET exists to fix. Your advantage over AFET: you
read the sentence directly, so you resolve context natively. Use it. Always ask
"what does *this sentence* tell me about the entity?" before assigning a type.

## Output contract: a type-path, possibly partial

A type assignment is a **path from the root down the hierarchy**, e.g.
`person → artist → actor`. Two rules govern where the path stops:

1. **It need not reach a leaf.** If context supports `person → artist` but does
   not say *which kind* of artist, stop at `artist`. Inventing `actor` vs
   `singer` when the sentence doesn't disambiguate is a typing error, not
   thoroughness. AFET stops its top-down walk exactly when confidence in the
   next level drops below a threshold — mirror that judgement.
2. **One path per mention by default.** Multiple types on one mention should
   form a single path (`person`, then `artist`, then `actor`), not unrelated
   siblings. Only emit two separate paths if the context genuinely supports two
   independent roles (rare).

## Procedure

Work one mention at a time. For each mention:

### 1. Establish the hierarchy
If the user supplied a type hierarchy/ontology, use it verbatim — it is the
source of truth. If they did not, use the bundled default in
`references/type-hierarchy.md` (a Freebase-derived hierarchy in the style AFET
used: person/organization/location/product/... with fine-grained children).
State which hierarchy you're using so the user can swap it.

### 2. Read the local context, extract signal
Identify the mention span, then gather the same kinds of evidence AFET's
features captured (`references/feature-cues.md` has the full list). The
high-value ones:
- **Head word** of the mention and the **words immediately before/after** it
  ("Governor ___", "___ gives a speech", "star ___").
- **Apposition / role words** ("the actor X", "X, a senator").
- **Verbs and objects** the mention participates in ("invested", "starred in",
  "was elected").

### 3. Walk the tree top-down
Start at the root. Among the children, pick the one the context best supports.
Descend. Repeat. **Stop** when either you reach a leaf, or the context no longer
clearly favors one child over its siblings — emit the path so far. This top-down
walk is what makes the output a coherent path and prevents contradictory types
(you can't pick `actor` without having committed to `artist → person` above it).

### 4. Emit with brief justification
For each mention give the path and one short phrase of evidence, so the typing
is auditable:

```
"Schwarzenegger" → person → artist → actor   (cue: "action-movie star")
```

## Output format

Default to this table unless the user asks for JSON or another shape:

| Mention | Type-path | Context cue |
|---------|-----------|-------------|
| Schwarzenegger | person → artist → actor | "action-movie star" |

When the user wants machine-readable output (building a dataset, feeding a
pipeline), emit JSON instead:

```json
[
  {"mention": "Schwarzenegger", "span": [4, 5],
   "type_path": ["person", "artist", "actor"], "cue": "action-movie star"}
]
```

## When you're unsure

- **Context underdetermines the fine type** → stop higher on the path. Partial
  is correct; guessing is not.
- **Entity not in the hierarchy at all** → type to the nearest ancestor that
  fits, and flag it. Don't force a bad leaf.
- **Mention is ambiguous between two top-level types** (is "Washington" a person
  or location?) → resolve from context; if context truly can't, say so rather
  than pick the popular one. (AFET's whole critique is that defaulting to the
  popular type is the central failure mode.)

## What this skill deliberately does NOT do

It does not reproduce AFET's training pipeline (partial-label embedding,
adaptive-margin rank loss, Brown-cluster features, the iterative optimizer).
Those exist to learn a classifier from noisy distant-supervision labels without
reading the text. You read the text, so you don't need them. If the user
specifically wants to *reimplement AFET's algorithm* or train a model, that's a
different task — point them to the paper's Section 3 and the authors' code
(github.com/shanzhenren/AFET) rather than using this skill.
