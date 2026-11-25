"""Refresh the place count per state in data/states.json. Run from anywhere."""
import json, os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
S = json.load(open('data/states.json'))
for s in S: s['count'] = len(json.load(open(f"data/places/{s['slug']}.json"))['places'])
json.dump(S, open('data/states.json', 'w'), ensure_ascii=False, indent=1)
print('total', sum(s['count'] for s in S))
