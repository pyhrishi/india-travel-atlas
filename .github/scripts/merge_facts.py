#!/usr/bin/env python3
"""Fail-closed merge of all 36 independently verified region artifacts."""
import glob
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ART = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "region-artifacts")
FACTS = os.path.join(ROOT, "data", "facts")
STATE_DIR = os.path.join(ROOT, ".github", "facts-state")

EXPECTED = {
    "andhra-pradesh", "arunachal-pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal-pradesh", "jharkhand", "karnataka",
    "kerala", "madhya-pradesh", "maharashtra", "manipur", "meghalaya",
    "mizoram", "nagaland", "odisha", "punjab", "rajasthan", "sikkim",
    "tamil-nadu", "telangana", "tripura", "uttar-pradesh", "uttarakhand",
    "west-bengal", "andaman-and-nicobar-islands", "chandigarh",
    "dadra-and-nagar-haveli-and-daman-and-diu", "delhi",
    "jammu-and-kashmir", "ladakh", "lakshadweep", "puducherry",
}

def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)

if not os.path.isdir(ART):
    raise SystemExit(f"Artifact directory missing: {ART}")

folders = {
    os.path.basename(path)[len("region-"):]: path
    for path in glob.glob(os.path.join(ART, "region-*"))
    if os.path.isdir(path)
}
missing = sorted(EXPECTED - set(folders))
unexpected = sorted(set(folders) - EXPECTED)
if missing or unexpected:
    raise SystemExit(
        "Refusing partial/invalid publish. "
        f"Missing regions: {missing}; unexpected regions: {unexpected}"
    )

# Validate every artifact completely before changing any tracked output.
validated = {}
for slug in sorted(EXPECTED):
    folder = folders[slug]
    fact_path = os.path.join(folder, "data", "facts", slug + ".json")
    state_path = os.path.join(folder, ".github", "facts-state", slug + ".json")
    if not os.path.isfile(fact_path) or not os.path.isfile(state_path):
        raise SystemExit(f"Refusing publish: {slug} artifact lacks facts or checkpoint")
    facts = load_json(fact_path)
    state = load_json(state_path)
    if not isinstance(facts, dict) or not isinstance(state, dict):
        raise SystemExit(f"Refusing publish: malformed JSON for {slug}")
    for key in ("r", "m", "h"):
        if not isinstance(state.get(key), dict):
            raise SystemExit(f"Refusing publish: {slug} checkpoint has no valid {key!r} map")
    validated[slug] = (fact_path, state_path, facts, state)

# Ensure every catalogue place has an explicit terminal state: an article match,
# an OSM/manual match, or a recorded miss. An interrupted region cannot pass.
catalogue = {}
for place_path in sorted(glob.glob(os.path.join(ROOT, "data", "places", "*.json"))):
    slug = os.path.basename(place_path)[:-5]
    places = load_json(place_path).get("places", [])
    if slug not in EXPECTED:
        raise SystemExit(f"Catalogue contains unexpected region: {slug}")
    catalogue[slug] = places

for slug, places in catalogue.items():
    facts, state = validated[slug][2], validated[slug][3]
    terminal = set(state["r"]) | set(state["m"])
    for place in places:
        key = f"{slug}:{place['n']}"
        if key not in terminal:
            raise SystemExit(f"Refusing partial publish: {key} has no terminal verification status")
        # Article evidence must be a Wikipedia article title, not an OSM-only record.
        if str(place["n"]) in facts and facts[str(place["n"])].get("w"):
            continue
        # Missing article matches are valid only after explicit miss/OSM disposition.
        if key not in state["m"] and not state["r"].get(key, {}).get("osm"):
            raise SystemExit(f"Refusing publish: {key} has no article evidence or documented fallback")

os.makedirs(FACTS, exist_ok=True)
os.makedirs(STATE_DIR, exist_ok=True)
for slug, (fact_path, state_path, _facts, _state) in validated.items():
    shutil.copy2(fact_path, os.path.join(FACTS, slug + ".json"))
    shutil.copy2(state_path, os.path.join(STATE_DIR, slug + ".json"))

# Rebuild the queue only after all 36 regions pass validation.
unverified = []
for slug, places in catalogue.items():
    facts = validated[slug][2]
    for place in places:
        article = facts.get(str(place["n"]), {})
        if not article.get("w"):
            unverified.append({
                "k": f"{slug}:{place['n']}",
                "name": place["name"],
                "district": place.get("district", ""),
                "state": slug,
                "category": place.get("category", ""),
            })
with open(os.path.join(FACTS, "_unverified.json"), "w", encoding="utf-8") as handle:
    json.dump(unverified, handle, ensure_ascii=False, separators=(",", ":"))

print(
    f"Validated and merged all {len(validated)} regions; "
    f"global article-unverified queue contains {len(unverified)} places."
)
