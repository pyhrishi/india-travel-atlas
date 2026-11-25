#!/usr/bin/env python3
"""Verify every atlas place against its own Wikipedia article and Wikidata, and save data/facts/<state>.json.

Matching is strict, so the summary, link and photo are about the place itself, not the town or district:
  - the article's title must share a distinctive word with the place name (or match it exactly), and
  - the article's coordinates must be within 15 km (25 km for an exact title match);
  - articles that are about the state, the district or a broad region are rejected.
Places with no matching article are listed in data/facts/_unverified.json for manual checking.
Runs on GitHub Actions (the app's sandbox cannot reach Wikipedia). Incremental: re-checks a place
when its name or position changes, or after 60 days.
"""
import json, os, re, sys, time, math, glob, urllib.parse, urllib.request, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTD = os.path.join(ROOT, 'data', 'facts')
STATE = os.path.join(ROOT, '.github', 'facts-state.json')
UA = 'IndiaTravelAtlas/1.0 (https://pyhrishi.github.io/india-travel-atlas/; github.com/pyhrishi)'
API = 'https://en.wikipedia.org/w/api.php'
WD = 'https://www.wikidata.org/w/api.php'
FORCE = '--force' in sys.argv
NOW = int(time.time()); DAY = 86400
START = time.time(); BUDGET = 150*60  # stop searching after this, save, and let the next run continue
OSMF = [0]  # consecutive OpenStreetMap failures; after 3 we stop asking it this run

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
            time.sleep(0.12)
            return j
        except Exception:
            time.sleep(3 * (i + 1))
    return {}

def km(a, b):
    r = math.pi / 180
    d = math.sin((b[0]-a[0])*r/2)**2 + math.cos(a[0]*r)*math.cos(b[0]*r)*math.sin((b[1]-a[1])*r/2)**2
    return 12742 * math.asin(math.sqrt(d))

GENERIC = set('the of and at in on near old new great big little sri shri shree swami saint st temple temples mandir mandiram devi mata fort forts qila garh lake lakes tal talab falls fall waterfall waterfalls beach beaches hill hills peak park national sanctuary wildlife reserve tiger bird museum palace mahal church cathedral basilica mosque masjid dargah gurdwara sahib dam river valley village island islands cave caves garden gardens tomb maqbara ghat ghats kund tank stepwell baori math mutt ashram monastery gompa stupa memorial market bazaar beach road station viewpoint point trek trail circuit complex area town city district state region india indian north south east west central upper lower'.split())
def norm(s):
    s = s.lower()
    s = re.sub(r'\(.*?\)', ' ', s)
    return re.sub(r'[^a-z0-9 ]+', ' ', s)
def sig(s):
    return {w for w in norm(s).split() if len(w) >= 4 and w not in GENERIC}
def strip_name(n):
    return re.sub(r'\s*\(.*?\)\s*', ' ', n).strip()

def variants(name):
    base = strip_name(name)
    out = [base]
    for sep in [' & ', ' and ', ', ', ' – ', ' - ']:
        if sep in base:
            out.append(base.split(sep)[0].strip())
    m = re.search(r'\((.*?)\)', name)
    if m: out.append(m.group(1).strip())
    seen = []; [seen.append(v) for v in out if v and v not in seen]
    return seen

PROPS = dict(prop='coordinates|pageprops|info|pageimages', ppprop='disambiguation|wikibase_item', inprop='url',
             piprop='thumbnail|name', pithumbsize='960', pilicense='free', colimit='max')

BADT = re.compile(r'constituency|assembly|lok sabha|vidhan sabha|\bmetro\b|university|college|school|institute|railway station|airport|\bdistrict\b|tehsil|taluk|\bblock\b|mandal|municipal|corporation|election|hospital|\((film|novel|song|tv series|album)|cricket|football|company|limited|\bparty\b|list of|division', re.I)
def good(pg, p, exact, broad):
    if not pg or 'missing' in pg or 'invalid' in pg: return False
    if 'disambiguation' in (pg.get('pageprops') or {}): return False
    t = pg['title']; nt = norm(t).strip()
    if BADT.search(t) and not BADT.search(p['name']): return False
    if nt in broad and nt not in {norm(v).strip() for v in variants(p['name'])}: return False
    c = (pg.get('coordinates') or [None])[0]
    loc = sig(p.get('dist', '')) | sig(p.get('st', ''))
    tw, pw = sig(t), sig(p['name']) - loc
    exact_title = nt in {norm(v).strip() for v in variants(p['name'])}
    if not exact_title and not (tw & pw): return False
    if c:
        d = km(p['ll'], (c['lat'], c['lon']))
        return d <= (25 if exact_title else 15)
    return exact_title and exact and bool(pw)  # no coordinates: only accept an exact, distinctive title

OVP = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
def osm(p):
    """Look for a mapped feature near the place whose name shares a distinctive word with it."""
    loc = sig(p.get('dist', '')) | sig(p.get('st', ''))
    words = sorted(sig(p['name']) - loc, key=len, reverse=True)
    if not words or OSMF[0] >= 3: return None
    w = re.escape(words[0])
    q = f'[out:json][timeout:25];nwr(around:5000,{p["ll"][0]},{p["ll"][1]})["name"~"{w}",i];out tags center 8;'
    for i in range(2):
        url = OVP[i % 2]
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({'data': q}).encode(), headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=20) as r: j = json.load(r)
            OSMF[0] = 0; time.sleep(1.1)
            for e in j.get('elements', []):
                nm = (e.get('tags') or {}).get('name:en') or (e.get('tags') or {}).get('name', '')
                if sig(nm) & set(words):
                    t = e.get('tags') or {}
                    out = {'osm': f"{e['type']}/{e['id']}", 'on': nm}
                    if t.get('website'): out['web'] = t['website']
                    if t.get('wikipedia'): out['wpt'] = t['wikipedia']
                    return out
            return None
        except Exception:
            time.sleep(2)
    OSMF[0] += 1
    if OSMF[0] == 3: print('OpenStreetMap not answering; skipping it for the rest of this run', flush=True)
    return None

def main():
    states = {s['slug']: s['name'] for s in json.load(open(os.path.join(ROOT, 'data', 'states.json')))}
    places = []
    broad = {norm(n).strip() for n in states.values()} | {'india'}
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'places', '*.json'))):
        slug = os.path.basename(f)[:-5]
        for p in json.load(open(f))['places']:
            places.append(dict(k=f"{slug}:{p['n']}", slug=slug, n=p['n'], name=p['name'], dist=p.get('district', ''),
                               st=states.get(slug, ''), cat=p.get('category', ''), ll=(p['lat'], p['lng'])))
            broad.add(norm(p.get('district', '')).strip()); broad.add(norm(p.get('district', '') + ' district').strip())
    old = json.load(open(STATE)) if os.path.exists(STATE) else {}
    R = old.get('r', {}); M = old.get('m', {}); H = old.get('h', {}); PEND = old.get('p', {}); M2 = set(old.get('m2', []))
    fp = lambda p: hashlib.md5(f"{p['name']}|{p['ll'][0]:.3f}|{p['ll'][1]:.3f}".encode()).hexdigest()[:10]
    keys = {p['k'] for p in places}
    R = {k: v for k, v in R.items() if k in keys}; M = {k: v for k, v in M.items() if k in keys}
    MV = 2  # matching rules version; results from older rules get re-checked
    todo = [p for p in places if FORCE or (p['k'] in R and R[p['k']].get('mv', 1) < MV) or (p['k'] in M and p['k'] not in M2) or H.get(p['k']) != fp(p) or (p['k'] in M and NOW - M[p['k']] > 60*DAY)
            or (p['k'] in R and NOW - R[p['k']].get('at', 0) > 60*DAY) or (p['k'] not in R and p['k'] not in M)]
    hit = {k: v for k, v in PEND.items() if k in keys}
    todo = [p for p in todo if p['k'] not in hit]
    print(f'{len(places)} places, {len(todo)} to check, {len(hit)} matched earlier and waiting for details', flush=True)
    KEEP = ('title', 'fullurl', 'pageprops', 'thumbnail', 'pageimage', 'coordinates')
    def checkpoint():
        pend = {k: {x: pg[x] for x in KEEP if x in pg} for k, pg in hit.items() if k not in R or R[k].get('osm') or R[k].get('mv', 1) < MV}
        json.dump({'v': 1, 'r': R, 'm': M, 'h': H, 'p': pend, 'm2': sorted(M2 & set(M))}, open(STATE, 'w'), ensure_ascii=False, separators=(',', ':'))
        print(f'checkpoint: {len(R)} done, {len(pend)} waiting, {len(M)} unmatched', flush=True)
    import signal
    def bye(*a):
        checkpoint(); sys.exit(0)
    signal.signal(signal.SIGTERM, bye); signal.signal(signal.SIGINT, bye)
    # 1) direct titles (all name variants), 40 titles per request
    reqs = []
    for p in todo:
        for v in variants(p['name']): reqs.append((v, p))
    for i in range(0, len(reqs), 40):
        chunk = reqs[i:i+40]; titles = sorted({v for v, _ in chunk})
        j = get(API, dict(PROPS, action='query', redirects='1', titles='|'.join(titles)))
        q = j.get('query', {}); alias = {t: t for t in titles}
        for n in q.get('normalized', []) + q.get('redirects', []):
            for t in alias:
                if alias[t] == n['from']: alias[t] = n['to']
        pages = {pg['title']: pg for pg in q.get('pages', {}).values()}
        for v, p in chunk:
            if p['k'] in hit: continue
            pg = pages.get(alias[v])
            if good(pg, p, True, broad): hit[p['k']] = pg
    print(f'titles: {len(hit)} matched', flush=True)
    for p in todo:
        if p['k'] in hit: H[p['k']] = fp(p)
    checkpoint()
    # 2) search with district and state, 3) articles within 2 km that share a distinctive word
    rest = [p for p in todo if p['k'] not in hit]
    for n, p in enumerate(rest):
        if time.time() - START > BUDGET:
            print(f'time budget reached at {n}/{len(rest)}; saving, the next run continues from here', flush=True); break
        b = strip_name(p['name']).replace('&', ' ')
        got = None
        for qs in (f"{b} {p['dist']}", f"{b} {p['st']}", b):
            j = get(API, dict(PROPS, action='query', generator='search', gsrlimit='6', gsrnamespace='0', gsrsearch=qs))
            for pg in sorted(j.get('query', {}).get('pages', {}).values(), key=lambda g: g.get('index', 9)):
                if good(pg, p, False, broad): got = pg; break
            if got: break
        if not got:
            j = get(API, dict(PROPS, action='query', generator='geosearch', ggscoord=f"{p['ll'][0]}|{p['ll'][1]}", ggsradius='2000', ggslimit='15'))
            for pg in j.get('query', {}).get('pages', {}).values():
                if good(pg, p, False, broad): got = pg; break
        if got: hit[p['k']] = got
        else:
            o = osm(p)
            if o: R[p['k']] = dict(o, at=NOW, mv=2); M.pop(p['k'], None)
            else: M[p['k']] = NOW; M2.add(p['k']); R.pop(p['k'], None)
        H[p['k']] = fp(p)
        if n % 150 == 0:
            print(f'search {n}/{len(rest)}: {len(hit)} matched', flush=True); checkpoint()
    for p in todo:
        if p['k'] in hit: H[p['k']] = fp(p)
    # 4) summaries (intro, plain text), 20 per request
    titles = sorted({pg['title'] for pg in hit.values()})
    ext = {}
    for i in range(0, len(titles), 20):
        j = get(API, dict(action='query', prop='extracts', exintro='1', explaintext='1', exsentences='5', exlimit='20', redirects='1', titles='|'.join(titles[i:i+20])))
        for pg in j.get('query', {}).get('pages', {}).values():
            ext[pg.get('title')] = re.sub(r'\s+', ' ', (pg.get('extract') or '')).strip()
    # 5) Wikidata facts
    qids = sorted({(pg.get('pageprops') or {}).get('wikibase_item') for pg in hit.values()} - {None})
    claims = {}
    for i in range(0, len(qids), 50):
        j = get(WD, dict(action='wbgetentities', ids='|'.join(qids[i:i+50]), props='claims'))
        for q, e in (j.get('entities') or {}).items(): claims[q] = e.get('claims', {})
    def vals(c, prop):
        out = []
        for s in c.get(prop, []):
            dv = ((s.get('mainsnak') or {}).get('datavalue') or {}).get('value')
            if dv is not None: out.append(dv)
        return out
    need = set()
    for c in claims.values():
        for v in vals(c, 'P1435') + vals(c, 'P31')[:3]:
            if isinstance(v, dict) and v.get('id'): need.add(v['id'])
    labels = {}
    need = sorted(need)
    for i in range(0, len(need), 50):
        j = get(WD, dict(action='wbgetentities', ids='|'.join(need[i:i+50]), props='labels', languages='en'))
        for q, e in (j.get('entities') or {}).items(): labels[q] = ((e.get('labels') or {}).get('en') or {}).get('value', '')
    for k, pg in hit.items():
        q = (pg.get('pageprops') or {}).get('wikibase_item'); c = claims.get(q, {})
        r = {'w': pg['title'], 'u': pg.get('fullurl', ''), 'x': ext.get(pg['title'], ''), 'q': q or '', 'at': NOW, 'mv': 2}
        web = [v for v in vals(c, 'P856') if isinstance(v, str)]
        if web: r['web'] = web[0]
        her = [labels.get(v['id'], '') for v in vals(c, 'P1435') if isinstance(v, dict)]
        her = [h for h in her if h]
        if her: r['her'] = sorted(set(her))[:3]
        el = [v for v in vals(c, 'P2044') if isinstance(v, dict) and 'amount' in v]
        if el:
            try: r['el'] = round(float(el[0]['amount']))
            except Exception: pass
        inc = [v for v in vals(c, 'P571') if isinstance(v, dict) and 'time' in v]
        if inc:
            t = inc[0]['time']; pr = inc[0].get('precision', 9)
            y = int(t[1:t.index('-', 1)]) * (-1 if t.startswith('-') else 1)
            r['inc'] = f"{abs(y)} BCE" if y < 0 else (f"{(y-1)//100+1}th century" if pr <= 7 else str(y))
        inst = [labels.get(v['id'], '') for v in vals(c, 'P31')[:3] if isinstance(v, dict)]
        inst = [x for x in inst if x]
        if inst: r['is'] = inst
        th = pg.get('thumbnail')
        if th and pg.get('pageimage'): r['img'] = th['source']; r['file'] = pg['pageimage']
        R[k] = r; M.pop(k, None)
    os.makedirs(OUTD, exist_ok=True)
    by = {}
    for p in places:
        r = R.get(p['k'])
        if r: by.setdefault(p['slug'], {})[str(p['n'])] = {k: v for k, v in r.items() if k not in ('at', 'mv')}
    for slug in {p['slug'] for p in places}:
        json.dump(by.get(slug, {}), open(os.path.join(OUTD, slug + '.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    unv = [{'k': p['k'], 'name': p['name'], 'district': p['dist'], 'state': p['st'], 'category': p['cat']} for p in places if p['k'] not in R]
    json.dump(unv, open(os.path.join(OUTD, '_unverified.json'), 'w'), ensure_ascii=False, indent=0)
    json.dump({'v': 1, 'r': R, 'm': M, 'h': H, 'p': {}, 'm2': sorted(M2 & set(M))}, open(STATE, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f'done: {len(R)} verified, {len(unv)} unverified', flush=True)

if __name__ == '__main__':
    main()
