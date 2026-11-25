#!/usr/bin/env python3
"""Refresh the Atlas current country/area registry from the UN Statistics Division M49 overview."""
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://unstats.un.org/unsd/methodology/m49/overview/"
OUT = Path("data/entities/current.json")

class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None
    def handle_starttag(self, tag, attrs):
        if tag == "table" and self.table is None:
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None

def clean_code(value, width):
    value = re.sub(r"[^0-9]", "", value)
    return value.zfill(width) if value else None

def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "HrishikeshAtlas/1.0 (M49 registry refresh)"})
    with urllib.request.urlopen(req, timeout=40) as response:
        html = response.read().decode("utf-8", "replace")
    parser = Tables()
    parser.feed(html)
    rows = None
    for table in parser.tables:
        for i, row in enumerate(table):
            header = " | ".join(row).lower()
            if "country or area" in header and "m49 code" in header and "iso-alpha2 code" in header and "iso-alpha3 code" in header:
                rows = (table, i)
                break
        if rows:
            break
    if not rows:
        raise SystemExit("Could not locate the expected UN M49 table; refusing to overwrite registry.")
    table, header_i = rows
    header = [x.lower() for x in table[header_i]]
    def col(*needles):
        for i, name in enumerate(header):
            if all(n in name for n in needles):
                return i
        raise ValueError("Missing M49 column: " + repr(needles))
    name_i, m49_i, iso2_i, iso3_i = col("country or area"), col("m49 code"), col("iso-alpha2"), col("iso-alpha3")
    entities = []
    seen = set()
    for row in table[header_i + 1:]:
        if max(name_i, m49_i, iso2_i, iso3_i) >= len(row):
            continue
        name = row[name_i].strip()
        m49 = clean_code(row[m49_i], 3)
        iso2 = row[iso2_i].strip().upper() or None
        iso3 = row[iso3_i].strip().upper() or None
        if not name or not m49 or m49 in seen:
            continue
        seen.add(m49)
        entities.append({
            "id": "m49:" + m49,
            "name": name,
            "m49": m49,
            "iso2": iso2,
            "iso3": iso3,
            "entity_type": "m49-country-or-area",
            "status_note": "UN M49 statistical country-or-area entry; inclusion does not imply sovereignty or political affiliation.",
            "source": URL
        })
    if len(entities) < 200:
        raise SystemExit(f"Only {len(entities)} M49 rows parsed; refusing to publish an incomplete registry.")
    # Keep stable local links for the two countries already represented in the Atlas.
    aliases = {"356": "country:in", "524": "country:np"}
    for entity in entities:
        if entity["m49"] in aliases:
            entity["id"] = aliases[entity["m49"]]
    payload = {
        "schema_version": 1,
        "standard": "UNSD M49",
        "source": URL,
        "source_note": "M49 is a statistical classification of countries or areas. It does not imply sovereignty, political affiliation, or boundary delimitation.",
        "entity_types": ["m49-country-or-area", "territory", "dependency", "special-administrative-area", "disputed-or-partially-recognised", "other-area"],
        "entities": sorted(entities, key=lambda e: e["name"].casefold()),
        "coverage": {"status": "m49-imported", "count": len(entities), "reviewed_at": __import__("datetime").date.today().isoformat(),
                     "note": "M49 countries and areas imported. Add separately sourced disputed or partially recognised entities as distinct records; never infer sovereignty from this list."}
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    json.loads(tmp.read_text(encoding="utf-8"))
    tmp.replace(OUT)
    print(f"Wrote {len(entities)} UN M49 country/area entities to {OUT}")

if __name__ == "__main__":
    main()
