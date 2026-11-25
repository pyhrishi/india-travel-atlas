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


## Global boundary display

The interactive world overview in `index.html` loads the generalised 1:110m country polygons from `world-atlas` (Natural Earth-derived) at runtime. Polygon IDs are matched to the three-digit UN M49 numeric codes in `data/entities/current.json`. The display reports how many registry entries have a polygon at this scale; it does not claim that every statistical area has a separate polygon. Small islands and areas may be omitted at 1:110m resolution.

Boundary geometry is a cartographic reference, not a legal boundary dataset. It must not be interpreted as a sovereignty, recognition, affiliation, or delimitation position. The boundary service is an external runtime dependency; if it is unavailable, the searchable entity registry remains usable. The India/Nepal administrative map and historical sites layer remain separate.


## Country-level administrative boundaries

The World explorer can request first-level administrative boundaries (ADM1) for a selected entity using the geoBoundaries current `gbOpen` API. The application reads the API metadata, uses its simplified GeoJSON URL, and displays the source, represented year, and licence returned for that specific country/layer. geoBoundaries documents the endpoint as `/api/current/gbOpen/[ISO3]/[ADM-LEVEL]/`; coverage and source/licence vary by country. This is an on-demand layer, not a claim that all 248 M49 entries have ADM1 coverage. The API is an external runtime dependency and the UI reports unavailable layers without disabling the entity registry. Attribution: geoBoundaries and the primary data provider named in the returned metadata.


## Administrative detail levels (ADM1–ADM5)

The World explorer offers on-demand ADM1 through ADM5 requests from the geoBoundaries `gbOpen` API. ADM1 is generally state/province level; ADM2 often corresponds to districts or counties, but the canonical unit name is country-specific and is displayed from the returned metadata. Coverage is not universal at every level. India ADM2 metadata currently reports 736 units (canonical: District; represented year 2021; source: Pathways Data Pvt. Ltd. and lgdirectory.gov.in; licence: ODbL 1.0). Nepal ADM2 metadata currently reports 75 units (canonical: Districts; represented year 2006; source: geoBoundaries/Wikimedia Commons; licence: Public Domain). These different vintages and licences must remain visible rather than implying a uniform current dataset. Administrative geometry is generalized and must not be presented as a sovereignty or legal delimitation statement.


The World explorer displays primary-source and licence-detail links from each geoBoundaries metadata response where those URLs are supplied. It also shows the source-data update date and dataset build date. A visible warning is added when the represented year is earlier than 2018; this is a conservative review prompt, not an assertion that newer data is necessarily authoritative. Selecting an administrative polygon highlights it and shows its source-provided name and available identifier. Before using a boundary for legal, operational, or current-government purposes, verify it against the relevant official authority.
