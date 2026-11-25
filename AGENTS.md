# Hrishikesh's Atlas (formerly India Travel Atlas): notes for coding agents

Live site: https://pyhrishi.github.io/india-travel-atlas/ (GitHub Pages serves the `main` branch root; there is no build step on GitHub).

## Levels
World → country → state/province → district → place. Countries live in `CC`/`CTRY` in index.html; each region in `data/states.json` has `cc` (`in` default, `np` Nepal). `S.cc` is the current scope (`w` = all countries); `S.states` is the scoped list and `S.ALL` everything. The magazine (`data/mag.json`) is India-only.

## What's where
- `index.html` — the whole app (HTML, CSS and JS in one file). Edit it directly.
- `data/places/<state-slug>.json` — every place, full detail. Shape: `{"places":[{...}]}`. Each place has
  `n` (number, unique within the state, never reuse or renumber), `name`, `district`, `category`, `g` (group),
  `lat`, `lng`, `why` (one-line description), `tier` (`icon` | `top` | `gem`), `months` ([from, to]), `time`,
  and optional detail objects: `trek`, `park`, `wet`, `bird`, `cave`, `sky`, `rail`, `drive`, `gi`, `art`, `eat`,
  `beach`, `fall`, `fort`, `wild`, `stay`, `circ`.
- `data/index.json` — compact index of all places, **generated** by `tools/build_index.py`. Never hand-edit.
- `data/states.json` — state list with `count`, refreshed by `tools/update_counts.py`.
- `data/facts/<state>.json` and `data/facts/_unverified.json` — **written by the "Verify places" GitHub Action**
  (`.github/scripts/facts.py`). Each entry keyed by place `n`: `w` = matched Wikipedia title, `u` = URL, `x` = extract,
  `ll` = article coordinates. `_unverified.json` lists places with no matching article. Read these; don't edit them.
- `data/photos.json`, `data/photo-credits.json` — written by the photo Actions. Don't edit.
- `data/reach.json` — nearest station/airport per place (precomputed). New places without an entry simply show no "Getting there" card.
- `sw.js` — service worker. After changing data or `index.html`, run `python3 tools/bump_sw.py` so installed apps refresh their offline copy.

## After changing place data
```
python3 tools/build_index.py      # needed when name, lat/lng, category, tier, months, time, district or detail fields change
python3 tools/update_counts.py    # needed when places are added or removed
python3 tools/bump_sw.py
```
`why` lives only in `data/places/*.json`, so a description-only change needs just `bump_sw.py`.

## Rules
- Write JSON with `ensure_ascii=False, indent=1` to keep diffs small.
- Always `git pull --rebase` before you start and before you push: the GitHub Actions commit to `data/facts/` and `data/photos.json` often.
- Every push to `main` triggers the "Verify places" workflow; a new waiting run replaces an older waiting one. Batch your changes into few pushes.
- Never delete a place without the owner (Hrishikesh) approving the list first.
- Facts must be checkable: when you change a description, base it on the matched Wikipedia article (`data/facts`) or another reliable source. No marketing words ("must-visit", "breathtaking", "hidden gem").
- Indian English spelling; place names as commonly signposted.
- Test by serving the folder (`python3 -m http.server`) and opening it in a browser; check the console for errors.

## Verification pipeline safety and recovery
- `.github/workflows/facts.yml` verifies one region per matrix job (maximum five in parallel). Each region owns `.github/facts-state/<slug>.json`; never reintroduce a shared checkpoint writer in parallel jobs.
- Region workers checkpoint before external requests and periodically during search. They make three bounded attempts and upload the region facts plus checkpoint after each attempt. Automatic whole-workflow recovery is handled by `.github/workflows/retry-facts.yml` (up to three workflow attempts).
- The central publish job must run only after every matrix job succeeds. `.github/scripts/merge_facts.py` must fail closed unless all 36 expected region artifacts exist and every catalogue place has an explicit terminal disposition. Do not weaken this guard to publish partial output.
- Photo verification is part of the central publish job. Commons API batch failures must fail closed so the previous committed photo data remains intact. The separate photo workflow is scheduled/manual only and shares the facts concurrency group; do not add an independent push trigger that can race the central publisher.
- A queued/pending Actions run is not proof that jobs started. Confirm the matrix jobs, artifacts, merge summary, and deployment status before reporting completion. If a run fails, inspect its uploaded region artifacts and rerun failed work; never claim all places are verified merely because the workflow succeeded.
