# Current geographical entities registry

The Atlas separates **current geographical entities** from destination records.

- `current.json` is the registry contract and initial India/Nepal seed.
- Use UN Statistics Division M49 as the baseline for countries or areas and its regional groupings.
- M49 is a statistical list, not a statement about sovereignty, political affiliation, or boundaries.
- Supplement M49 with dependencies, territories, special administrative areas, and disputed or partially recognised entities using explicit `entity_type` and neutral `status_note` fields.
- Keep ISO codes and M49 codes as identifiers, not as political-status labels.
- Never merge historical polities into this current registry. Historical empires, kingdoms, states, and civilisations belong in `data/historical/`.
- Before publishing an entity, record a source and review date. Boundary datasets must carry their own source, version, and dispute/claim metadata.

The first seed contains India and Nepal because those are the countries already represented by the destination catalogue. It is not yet a complete world registry.
