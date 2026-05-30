# Default Type Hierarchy

A compact, Freebase-derived hierarchy in the style AFET used (the paper's Wiki
set had 113 types; OntoNotes 89; BBN 47). This is a usable default — when the
user gives their own ontology, prefer theirs and ignore this file.

Read a path top-down: `person → artist → actor`. A mention may stop at any
level when context doesn't justify going deeper.

```
root
├── person
│   ├── artist        → actor, singer, author, music
│   ├── athlete
│   ├── politician
│   ├── businessman
│   ├── doctor
│   ├── engineer
│   ├── scientist
│   ├── religious_leader
│   ├── coach
│   ├── soldier
│   └── title         (e.g. honorific roles)
├── organization
│   ├── company       → news_agency, broadcast, transit
│   ├── educational_institution
│   ├── government     → political_party
│   ├── sports_team
│   ├── sports_league
│   ├── military
│   ├── non_profit
│   └── religious_organization
├── location
│   ├── city
│   ├── country
│   ├── province / state
│   ├── geography     → island, mountain, body_of_water, glacier
│   ├── structure     → airport, hospital, hotel, restaurant, sports_facility,
│   │                   theater, government_building
│   ├── transit       → railway, road, bridge
│   └── celestial / astral_body
├── product
│   ├── software
│   ├── car
│   ├── weapon
│   ├── ship
│   ├── airplane
│   ├── spacecraft
│   ├── instrument
│   └── camera
├── event
│   ├── election
│   ├── attack / military_conflict
│   ├── natural_disaster
│   ├── sports_event
│   └── protest
├── art
│   ├── film
│   ├── written_work   (book, newspaper, journal)
│   ├── music
│   ├── play
│   └── tv_program
├── building
│   (often overlaps with location → structure; pick whichever the user's
│    ontology defines — don't duplicate)
└── other
    ├── language
    ├── religion
    ├── ethnicity
    ├── award
    ├── currency
    ├── disease
    ├── god / deity
    └── living_thing   → animal, plant
```

## Notes for use

- **Type-paths, not flat labels.** `person → athlete` is a path; `athlete` alone
  is shorthand for the same path. Always anchor to a top-level type.
- **Stop early when unsure.** If the sentence shows someone is a `person` doing
  something organizational but not clearly which role, `person` is a valid
  answer. Don't fabricate `politician` vs `businessman`.
- **Overlap is real.** A stadium is `location → structure → sports_facility` and
  arguably `building`. Pick one consistent convention per task; if the user's
  ontology resolves it, follow that.
