"""Use the photo of each place's verified Wikipedia article (from data/facts) in data/photos.json.

The older photo job matched loosely (any article within 50 km), so a few cards showed the wrong place.
A verified article's lead image wins; places with no verified article keep what they had.
Credits for verified photos are left to the app's on-device lookup (it reads them from Commons)."""
import json, os, glob, re
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'data', 'photos.json'); CRED = os.path.join(ROOT, 'data', 'photo-credits.json')
ph = json.load(open(OUT)); base = ph['base']; P = ph['p']; miss = set(ph.get('miss', []))
cred = json.load(open(CRED)) if os.path.exists(CRED) else {}
def rel(u):
    u = u.split('?')[0].replace('https://thumb.wikimedia.org/', 'https://upload.wikimedia.org/')
    u = re.sub(r'/(\d+)px-', '/960px-', u)
    return u[len(base):] if u.startswith(base) else u
changed = added = same = 0
for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'facts', '*.json'))):
    slug = os.path.basename(f)[:-5]
    if slug.startswith('_'): continue
    for n, r in json.load(open(f)).items():
        if not r.get('img') or not r.get('w'): continue
        k = f'{slug}:{n}'; new = rel(r['img'])
        fn = (r.get('file') or r['img']).lower()
        if re.search(r'\.svg|\bmap\b|_map|map_|locator|location|flag|logo|emblem|seal|coat_of_arms|diagram|plan_of|bust|portrait', fn): continue  # not a picture of the place
        old = P.get(k)
        if old == new: same += 1; continue
        if old: changed += 1
        else: added += 1
        P[k] = new; miss.discard(k)
        cred[k] = {'f': r.get('file', ''), 'w': r['w']}
ph['p'] = dict(sorted(P.items())); ph['miss'] = sorted(miss)
json.dump(ph, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump(dict(sorted(cred.items())), open(CRED, 'w'), ensure_ascii=False, separators=(',', ':'))
print(f'photos from verified articles: {same} already right, {changed} replaced, {added} added; {len(P)} places have photos')
