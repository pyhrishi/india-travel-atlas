#!/usr/bin/env python3
"""Fetch and validate first-level administrative boundaries from geoBoundaries.

Usage:
  python3 tools/build_global_maps.py --iso2 BD,BT,LK,MV,MM
  python3 tools/build_global_maps.py --iso2 BD,BT --dry-run

The script is intentionally fail-closed: it writes no country file until the
metadata, GeoJSON, feature names, geometry and feature count have passed checks.
"""
import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "data", "entities", "current.json")
MAP_DIR = os.path.join(ROOT, "data", "maps")
INDEX = os.path.join(MAP_DIR, "index.json")
API = "https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM1/"
USER_AGENT = "IndiaTravelAtlas/1.0 (open geography data build)"


def get_json(url, attempts=3):
    last = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Could not retrieve {url}: {last}")


def first_record(value):
    if isinstance(value, list):
        if not value:
            raise ValueError("geoBoundaries returned an empty metadata list")
        return value[0]
    if not isinstance(value, dict):
        raise ValueError("geoBoundaries metadata is not an object")
    return value


def valid_position(pos):
    return (isinstance(pos, (list, tuple)) and len(pos) >= 2
            and isinstance(pos[0], (int, float)) and isinstance(pos[1], (int, float))
            and math.isfinite(pos[0]) and math.isfinite(pos[1])
            and -180 <= pos[0] <= 180 and -90 <= pos[1] <= 90)


def walk_positions(value):
    if not isinstance(value, list) or not value:
        return False, []
    if valid_position(value):
        return True, [value]
    points = []
    for child in value:
        ok, found = walk_positions(child)
        if not ok:
            return False, []
        points.extend(found)
    return bool(points), points


def normalize_feature(feature, iso3):
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise ValueError("A boundary item is not a GeoJSON Feature")
    geom = feature.get("geometry")
    if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("ADM1 feature has missing or unsupported polygon geometry")
    ok, points = walk_positions(geom.get("coordinates"))
    if not ok or not points:
        raise ValueError("ADM1 feature has invalid or empty coordinates")
    props = feature.get("properties") or {}
    name = (props.get("shapeName") or props.get("shapeNameAlt")
            or props.get("name") or props.get("NAME_1"))
    if not isinstance(name, str) or not name.strip():
        raise ValueError("ADM1 feature is missing its administrative-unit name")
    return {
        "type": "Feature",
        "properties": {
            "st_nm": name.strip(),
            "name": name.strip(),
            "boundary_id": props.get("shapeID") or props.get("shapeISO") or "",
            "country_iso3": iso3,
            "source_properties": {
                key: props[key] for key in ("shapeName", "shapeNameAlt", "shapeID",
                    "shapeGroup", "shapeType", "shapeISO", "shapeID")
                if key in props and isinstance(props[key], (str, int, float, type(None)))
            }
        },
        "geometry": geom
    }


def atomic_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    os.replace(tmp, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso2", required=True, help="Comma-separated ISO-3166-1 alpha-2 codes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    registry = json.load(open(REGISTRY, encoding="utf-8"))
    entities = {e["iso2"].upper(): e for e in registry["entities"]
                if e.get("iso2") and e.get("iso3")}
    requested = list(dict.fromkeys(x.strip().upper() for x in args.iso2.split(",") if x.strip()))
    if not requested or len(requested) > 10:
        raise SystemExit("Supply between 1 and 10 ISO2 codes per batch")
    unknown = [code for code in requested if code not in entities]
    if unknown:
        raise SystemExit("ISO2 code(s) absent from the M49 registry: " + ", ".join(unknown))

    os.makedirs(MAP_DIR, exist_ok=True)
    index = json.load(open(INDEX, encoding="utf-8")) if os.path.exists(INDEX) else {
        "schema_version": 1,
        "source": "geoBoundaries gbOpen",
        "source_url": "https://www.geoboundaries.org/api.html",
        "license_note": "geoBoundaries gbOpen is CC-BY 4.0 compatible; individual source licences are recorded per map.",
        "countries": {}
    }
    index.setdefault("countries", {})

    for code in requested:
        entity = entities[code]
        iso3 = entity["iso3"].upper()
        metadata = first_record(get_json(API.format(iso3=iso3)))
        if metadata.get("boundaryISO") != iso3 or metadata.get("boundaryType") != "ADM1":
            raise RuntimeError(f"{code}: API metadata identity/level mismatch")
        url = metadata.get("simplifiedGeometryGeoJSON") or metadata.get("gjDownloadURL")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise RuntimeError(f"{code}: no secure GeoJSON download URL in metadata")
        expected = int(metadata.get("admUnitCount") or 0)

        def read_layer(download_url):
            raw = get_json(download_url)
            if raw.get("type") != "FeatureCollection" or not isinstance(raw.get("features"), list):
                raise RuntimeError(f"{code}: downloaded object is not a GeoJSON FeatureCollection")
            return [normalize_feature(f, iso3) for f in raw["features"]]

        features = read_layer(url)
        # Some simplified exports omit small islands or administrative units.
        # Fall back to full-resolution geometry instead of accepting an incomplete map.
        if expected and len(features) != expected and url != metadata.get("gjDownloadURL"):
            full_url = metadata.get("gjDownloadURL")
            if isinstance(full_url, str) and full_url.startswith("https://"):
                features = read_layer(full_url)
                url = full_url
        if not features or (expected and len(features) != expected):
            raise RuntimeError(f"{code}: feature count mismatch (got {len(features)}, expected {expected})")
        names = [f["properties"]["name"].casefold() for f in features]
        if len(names) != len(set(names)):
            raise RuntimeError(f"{code}: duplicate ADM1 names; requires manual review")

        all_xy = []
        for feature in features:
            _, pts = walk_positions(feature["geometry"]["coordinates"])
            all_xy.extend(pts)
        bounds = [min(p[0] for p in all_xy), min(p[1] for p in all_xy),
                  max(p[0] for p in all_xy), max(p[1] for p in all_xy)]
        output = {
            "type": "FeatureCollection",
            "country": {"name": entity["name"], "iso2": code.lower(), "iso3": iso3,
                        "m49": entity["m49"]},
            "metadata": {
                "boundary_id": metadata.get("boundaryID", ""),
                "boundary_year": metadata.get("boundaryYearRepresented", ""),
                "boundary_source": metadata.get("boundarySource", ""),
                "boundary_license": metadata.get("boundaryLicense", ""),
                "license_source": metadata.get("licenseSource", ""),
                "build_date": metadata.get("buildDate", ""),
                "source": "geoBoundaries gbOpen",
                "source_url": "https://www.geoboundaries.org/api.html",
                "download_url": url
            },
            "bounds": bounds,
            "features": features
        }
        if args.dry_run:
            print(f"VALID {code} {entity['name']}: {len(features)} ADM1 features, bounds={bounds}")
            continue
        atomic_json(os.path.join(MAP_DIR, code.lower() + ".json"), output)
        index["countries"][code.lower()] = {
            "name": entity["name"], "iso3": iso3, "m49": entity["m49"],
            "map_status": "ready", "admin_level": "ADM1",
            "admin_unit_count": len(features), "boundary_year": output["metadata"]["boundary_year"],
            "boundary_source": output["metadata"]["boundary_source"],
            "boundary_license": output["metadata"]["boundary_license"],
            "data_file": f"data/maps/{code.lower()}.json",
            "validated_at": time.strftime("%Y-%m-%d", time.gmtime())
        }
        print(f"BUILT {code} {entity['name']}: {len(features)} ADM1 features")
        time.sleep(1)

    if not args.dry_run:
        atomic_json(INDEX, index)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
