#!/usr/bin/env python3
"""Find a Wikipedia/Commons photo for every place in the atlas and save data/photos.json.
Runs on GitHub Actions (the app's own sandbox cannot reach Wikipedia). Incremental: keeps found
photos, retries misses after 30 days. Rules match the app: an article's coordinates must be close
to the place (50 km for a direct title, 30 km for search, 3 km for nearby articles)."""
import json, os, re, sys, time, math, glob, urllib.parse, urllib.request, html
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'data', 'photos.json')          # small: key -> thumbnail path (loaded by the app at start)
CRED = os.path.join(ROOT, 'data', 'photo-credits.json')  # credits: loaded only on the credits screen
STATE = os.path.join(ROOT, '.github', 'photos-state.json')  # full records + miss timestamps for the job
BASE = 'https://upload.wikimedia.org/wikipedia/commons/thumb/'
UA = 'IndiaTravelAtlas/1.0 (https://pyhrishi.github.io/india-travel-atlas/; github.com/pyhrishi)'
API = 'https://en.wikipedia.org/w/api.php'
COM = 'https://commons.wikimedia.org/w/api.php'
FORCE = '--force' in sys.argv
DAY = 86400; NOW = int(time.time())

def get(url, params, tries=4):
    params = dict(params, format='json', maxlag='5')
    q = url + '?' + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            req = urllib.request.Request(q, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                j = json.load(r)
            if 'error' in j and j['error'].get('code') == 'maxlag':
                time.sleep(5 * (i + 1)); continue
            time.sleep(0.15)
            return j
        except Exception as e:
            time.sleep(3 * (i + 1))
    return {}

def km(a, b):
    r = math.pi / 180
    d = math.sin((b[0]-a[0])*r/2)**2 + math.cos(a[0]*r)*math.cos(b[0]*r)*math.sin((b[1]-a[1])*r/2)**2
    return 12742 * math.asin(math.sqrt(d))

PROPS = dict(prop='pageimages|coordinates|pageprops', piprop='thumbnail|name', pithumbsize='720',
             pilicense='free', ppprop='disambiguation', colimit='max')
def ok(pg):
    return pg and 'missing' not in pg and pg.get('thumbnail') and not ('disambiguation' in (pg.get('pageprops') or {}))
def coord(pg):
    c = (pg.get('coordinates') or [None])[0]
    return (c['lat'], c['lon']) if c else None
def rec(pg):
    return {'t': pg['thumbnail']['source'], 'f': pg['pageimage'], 'w': pg['title']}

STOP = set('the of and at in on temple fort lake falls waterfall beach hill hills park national sanctuary wildlife museum palace church mosque dargah gurdwara dam river valley village island cave caves sri shri mata devi mandir garden gardens tomb'.split())
def words(s):
    return {w for w in re.findall(r'[a-z]{4,}', s.lower()) if w not in STOP}

def main():
    states = {s['slug']: s['name'] for s in json.load(open(os.path.join(ROOT, 'data', 'states.json')))}
    places = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'places', '*.json'))):
        slug = os.path.basename(f)[:-5]
        for p in json.load(open(f))['places']:
            places.append(dict(k=f"{slug}:{p['n']}", name=p['name'], dist=p.get('district', ''), st=states.get(slug, ''),
                               ll=(p['lat'], p['lng'])))
    old = json.load(open(STATE)) if os.path.exists(STATE) else (json.load(open(OUT)) if os.path.exists(OUT) and json.load(open(OUT)).get('v') == 1 else {'p': {}, 'miss': {}})
    P, M = old.get('p', {}), old.get('miss', {})
    keys = {p['k'] for p in places}
    P = {k: v for k, v in P.items() if k in keys}; M = {k: v for k, v in M.items() if k in keys}
    todo = [p for p in places if FORCE or (p['k'] not in P and NOW - M.get(p['k'], 0) > 30*DAY)]
    print(f'{len(places)} places, {len(P)} with photos, {len(todo)} to look up', flush=True)
    found = {}
    # 1) direct titles, 50 at a time
    for i in range(0, len(todo), 50):
        batch = todo[i:i+50]
        tmap = {}
        for p in batch:
            t = re.sub(r'\s*\(.*?\)\s*', ' ', p['name']).strip()
            tmap.setdefault(t, []).append(p)
        j = get(API, dict(PROPS, action='query', redirects='1', titles='|'.join(tmap)))
        q = j.get('query', {}); alias = {t: t for t in tmap}
        for n in q.get('normalized', []) + q.get('redirects', []):
            for t in alias:
                if alias[t] == n['from']: alias[t] = n['to']
        pages = {pg['title']: pg for pg in q.get('pages', {}).values()}
        for t, ps in tmap.items():
            pg = pages.get(alias[t])
            if not ok(pg): continue
            c = coord(pg)
            for p in ps:
                if (c and km(p['ll'], c) <= 50) or (not c and alias[t] == t):
                    found[p['k']] = rec(pg)
    print(f'titles: {len(found)} found', flush=True)
    # 2) search, then 3) nearby articles
    for n, p in enumerate([p for p in todo if p['k'] not in found]):
        base = re.sub(r'\s*\(.*?\)\s*', ' ', p['name']).replace('&', ' ').strip()
        hit = None
        for qs in (f"{base} {p['dist']} {p['st']}", f"{base} {p['st']}"):
            j = get(API, dict(PROPS, action='query', generator='search', gsrlimit='5', gsrnamespace='0', gsrsearch=qs))
            cands = sorted(j.get('query', {}).get('pages', {}).values(), key=lambda g: g.get('index', 9))
            for pg in cands:
                c = coord(pg)
                if ok(pg) and c and km(p['ll'], c) <= 30:
                    hit = pg; break
            if hit: break
        if not hit:
            j = get(API, dict(PROPS, action='query', generator='geosearch', ggscoord=f"{p['ll'][0]}|{p['ll'][1]}",
                              ggsradius='3000', ggslimit='10'))
            w = words(base)
            for pg in j.get('query', {}).get('pages', {}).values():
                if ok(pg) and w & words(pg['title']):
                    hit = pg; break
        if hit: found[p['k']] = rec(hit)
        else: M[p['k']] = NOW
        if n % 200 == 0: print(f'search {n}: {len(found)} found', flush=True)
    # 4) credits from Commons
    files = sorted({r['f'] for r in found.values()})
    meta = {}
    for i in range(0, len(files), 50):
        j = get(COM, dict(action='query', prop='imageinfo', iiprop='extmetadata',
                          iiextmetadatafilter='Artist|LicenseShortName|LicenseUrl',
                          titles='|'.join('File:' + f for f in files[i:i+50])))
        for pg in j.get('query', {}).get('pages', {}).values():
            e = ((pg.get('imageinfo') or [{}])[0]).get('extmetadata', {})
            a = html.unescape(re.sub(r'<[^>]+>', '', (e.get('Artist') or {}).get('value', '')))
            meta[pg['title'][5:].replace(' ', '_')] = {'a': re.sub(r'\s+', ' ', a).strip()[:120],
                'l': (e.get('LicenseShortName') or {}).get('value', ''), 'lu': (e.get('LicenseUrl') or {}).get('value', '')}
    for k, r in found.items():
        r.update(meta.get(r['f'].replace(' ', '_'), {}))
        P[k] = r; M.pop(k, None)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({'v': 1, 'updated': NOW, 'p': dict(sorted(P.items())), 'miss': dict(sorted(M.items()))},
              open(STATE, 'w'), ensure_ascii=False, separators=(',', ':'))
    def rel(u):
        u = u.split('?')[0].replace('https://thumb.wikimedia.org/', 'https://upload.wikimedia.org/')
        return u[len(BASE):] if u.startswith(BASE) else u
    short = {k: rel(r['t']) for k, r in sorted(P.items())}
    json.dump({'v': 2, 'base': BASE, 'updated': NOW, 'p': short, 'miss': sorted(M)},
              open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
    json.dump({k: {x: r[x] for x in ('f', 'w', 'a', 'l', 'lu') if r.get(x)} for k, r in sorted(P.items())},
              open(CRED, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f'done: {len(P)} of {len(places)} places have photos ({len(found)} new)')

if __name__ == '__main__':
    main()
