#!/usr/bin/env python3
"""Merge independent region artifacts and rebuild the global unverified queue."""
import json, os, sys, glob, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ART = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'region-artifacts')
FACTS = os.path.join(ROOT, 'data', 'facts')
STATE_DIR = os.path.join(ROOT, '.github', 'facts-state')
os.makedirs(FACTS, exist_ok=True)
os.makedirs(STATE_DIR, exist_ok=True)
merged = []
for folder in sorted(glob.glob(os.path.join(ART, 'region-*'))):
    slug = os.path.basename(folder)[len('region-'):]
    fact_src = os.path.join(folder, 'data', 'facts', slug + '.json')
    state_src = os.path.join(folder, '.github', 'facts-state', slug + '.json')
    if os.path.isfile(fact_src):
        shutil.copy2(fact_src, os.path.join(FACTS, slug + '.json'))
        merged.append(slug)
    if os.path.isfile(state_src):
        shutil.copy2(state_src, os.path.join(STATE_DIR, slug + '.json'))
# Rebuild unverified across the entire catalogue; retain existing facts for regions
# whose matrix job did not finish or whose artifact was unavailable.
unverified = []
for place_file in sorted(glob.glob(os.path.join(ROOT, 'data', 'places', '*.json'))):
    slug = os.path.basename(place_file)[:-5]
    places = json.load(open(place_file, encoding='utf-8')).get('places', [])
    fact_file = os.path.join(FACTS, slug + '.json')
    facts = json.load(open(fact_file, encoding='utf-8')) if os.path.isfile(fact_file) else {}
    for p in places:
        if str(p['n']) not in facts:
            unverified.append({'k': f"{slug}:{p['n']}", 'name': p['name'],
                               'district': p.get('district',''), 'state': slug,
                               'category': p.get('category','')})
json.dump(unverified, open(os.path.join(FACTS, '_unverified.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=0)
print(f"Merged {len(merged)} region artifacts; global unverified queue contains {len(unverified)} places.")
