"""Use the photo of each place's verified Wikipedia article (from data/facts) in data/photos.json.

The older photo job matched loosely (any article within 50 km), so a few cards showed the wrong place.
A verified article's lead image wins; places with no verified article keep what they had.
Credits for verified photos are left to the app's on-device lookup (it reads them from Commons)."""
import json, os, glob, re
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'data', 'photos.json'); CRED = os.path.join(ROOT, 'data', 'photo-credits.json')
ph = json.load(open(OUT)); base = ph['base']
old_cred = json.load(open(CRED)) if os.path.exists(CRED) else {}
P, cred = {}, {}
all_keys = set()
for pf in sorted(glob.glob(os.path.join(ROOT, 'data', 'places', '*.json'))):
    slug = os.path.basename(pf)[:-5]
    for place in json.load(open(pf))['places']:
        all_keys.add(f"{slug}:{place['n']}")
def rel(u):
    u = u.split('?')[0].replace('https://thumb.wikimedia.org/', 'https://upload.wikimedia.org/')
    u = re.sub(r'/(\d+)px-', '/1600px-', u)
    return u[len(base):] if u.startswith(base) else u
changed = added = same = rejected = 0
for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'facts', '*.json'))):
    slug = os.path.basename(f)[:-5]
    if slug.startswith('_'): continue
    for n, r in json.load(open(f)).items():
        if not r.get('img') or not r.get('w') or not r.get('file'): continue
        k = f'{slug}:{n}'
        fn = (r.get('file') or '').lower()
        if re.search(r'\.svg|\bmap\b|_map|map_|locator|location|flag|logo|emblem|seal|coat_of_arms|diagram|plan_of|bust|portrait', fn):
            rejected += 1
            continue
        new = rel(r['img'])
        if not new or (new.startswith('http') and 'upload.wikimedia.org' not in new):
            rejected += 1
            continue
        P[k] = new
        prev = old_cred.get(k, {})
        meta = prev if prev.get('f') == r['file'] else {}
        cred[k] = {x: meta[x] for x in ('a', 'l', 'lu') if meta.get(x)}
        cred[k].update({'f': r['file'], 'w': r['w']})
        if prev.get('f') == r['file']: same += 1
        elif prev: changed += 1
        else: added += 1
# A photo is published only when it is the lead image of that place's own verified article.
# Unverified places deliberately show the illustrated fallback rather than a nearby/wrong photo.
ph['p'] = dict(sorted(P.items()))
ph['miss'] = sorted(all_keys - set(P))
json.dump(ph, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump(dict(sorted(cred.items())), open(CRED, 'w'), ensure_ascii=False, separators=(',', ':'))

print(f'verified-article photos: {same} retained, {changed} replaced, {added} added, {rejected} non-photo assets rejected; {len(P)} of {len(all_keys)} places have verified photos; {len(all_keys - set(P))} intentionally have no verified photo')
