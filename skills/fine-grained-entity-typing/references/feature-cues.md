# Context Cues for Typing a Mention

These are the textual signals AFET extracted as features (its Table 2). You don't
compute them as a feature vector — you read them. They're listed here as a
checklist so you don't overlook a decisive cue. The single most predictive ones
in practice are the **head word** and the **immediate context words**.

| Cue | What to look at | Why it disambiguates |
|-----|-----------------|----------------------|
| **Head** | Syntactic head token of the mention span | "President [Obama]" — head + title fixes the role |
| **Tokens** | The words inside the mention | "Apple Inc" vs "apple" |
| **Context (±1–2 words)** | Unigrams/bigrams immediately before and after | "Governor ___ gives", "___, the actor," — usually the deciding cue |
| **Apposition / role nouns** | "X, a senator", "the novelist X" | States the type explicitly |
| **Governing verb** | The verb the mention is subject/object of | "invested", "starred in", "was elected", "scored" |
| **POS** | Part of speech of the mention tokens | Proper noun vs common noun changes entity-hood |
| **Word shape** | Capitalization pattern (Aa, AA, Aa0) | "USS Enterprise" (ship) vs "Enterprise" the town |
| **Character trigrams** | Substrings of the head | Morphology hints ("-grad", "-burg" → place) |
| **Length** | Number of tokens | Multi-token spans bias toward orgs/products |
| **Dependency** | Stanford dependency on the head token | Subject-of "govern" vs object-of "buy" |

## How to use these

1. Find the **head** and the **±2 word window** first. These resolve most
   mentions on their own.
2. If still ambiguous, look for an **apposition / role noun** or the
   **governing verb** — these often state or strongly imply the type.
3. Only descend to a fine leaf (`actor` vs `singer`) when a cue actually
   supports it. The shallower cues (shape, length, trigrams) are tie-breakers,
   not primary evidence — don't let them push you to a confident leaf the
   sentence doesn't justify.

## Worked example

> "The fourth movie in the Predator series may see the return of **action-movie
> star Arnold Schwarzenegger** to the franchise."

- Head: *Schwarzenegger*; context-before: *action-movie star*; governing frame:
  *return … to the franchise*.
- "action-movie **star**" is the decisive role noun → `artist → actor`.
- Anchor to top level: `person`.
- **Result:** `person → artist → actor`, cue = "action-movie star". No reason to
  go further (e.g. to a specific film role), so stop.
