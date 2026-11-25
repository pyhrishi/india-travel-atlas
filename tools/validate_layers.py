#!/usr/bin/env python3
"""Validate cross-references between the current destination catalogue and thematic layers."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
states = json.loads((root / "data/states.json").read_text(encoding="utf-8"))
known = {}
for state in states:
    path = root / "data/places" / (state["slug"] + ".json")
    if not path.exists():
        continue
    doc = json.loads(path.read_text(encoding="utf-8"))
    known[state["slug"]] = {int(p["n"]): p for p in doc.get("places", [])}

history = json.loads((root / "data/historical/index.json").read_text(encoding="utf-8"))
seen = set()
for item in history.get("places", []):
    key = item.get("id")
    if not key or key in seen:
        raise SystemExit(f"Missing or duplicate historical ID: {key!r}")
    seen.add(key)
    slug = item.get("slug")
    number = item.get("n")
    if slug not in known or int(number) not in known[slug]:
        raise SystemExit(f"Historical reference does not resolve to a destination: {key}")
    place = known[slug][int(number)]
    if place["name"] != item.get("name"):
        raise SystemExit(f"Historical name mismatch for {key}: {item.get('name')!r} != {place['name']!r}")
    if item.get("period") not in history.get("periods", []):
        raise SystemExit(f"Unknown historical period for {key}")

registry = json.loads((root / "data/entities/current.json").read_text(encoding="utf-8"))
ids = [e.get("id") for e in registry.get("entities", [])]
if len(ids) != len(set(ids)):
    raise SystemExit("Duplicate current entity IDs")
for entity in registry.get("entities", []):
    if not entity.get("name") or not entity.get("entity_type") or not entity.get("source"):
        raise SystemExit(f"Incomplete current entity record: {entity}")
    if entity.get("m49") and (len(entity["m49"]) != 3 or not entity["m49"].isdigit()):
        raise SystemExit(f"Invalid M49 code: {entity['m49']}")
print(f"Validated {len(seen)} historical references and {len(ids)} current entity records.")
