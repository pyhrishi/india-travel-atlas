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
FACTS_STATE = os.environ.get('FACTS_STATE', '').strip()
STATE = os.path.join(ROOT, '.github', 'facts-state', FACTS_STATE + '.json') if FACTS_STATE else os.path.join(ROOT, '.github', 'facts-state.json')
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
# old and new names of the same town count as the same word (Wikipedia often keeps the older title)
RENAMES = {'mysore': 'mysuru', 'bangalore': 'bengaluru', 'belgaum': 'belagavi', 'bellary': 'ballari', 'bijapur': 'vijayapura', 'gulbarga': 'kalaburagi',
  'shimoga': 'shivamogga', 'tumkur': 'tumakuru', 'mangalore': 'mangaluru', 'hubli': 'hubballi', 'chikmagalur': 'chikkamagaluru', 'chickmagalur': 'chikkamagaluru',
  'hospet': 'hosapete', 'calcutta': 'kolkata', 'bombay': 'mumbai', 'madras': 'chennai', 'pondicherry': 'puducherry', 'trivandrum': 'thiruvananthapuram',
  'cochin': 'kochi', 'calicut': 'kozhikode', 'trichur': 'thrissur', 'cannanore': 'kannur', 'quilon': 'kollam', 'alleppey': 'alappuzha', 'palghat': 'palakkad',
  'trichy': 'tiruchirappalli', 'trichinopoly': 'tiruchirappalli', 'tanjore': 'thanjavur', 'tuticorin': 'thoothukudi', 'conjeevaram': 'kanchipuram', 'ooty': 'udhagamandalam', 'ootacamund': 'udhagamandalam',
  'allahabad': 'prayagraj', 'benares': 'varanasi', 'banaras': 'varanasi', 'gurgaon': 'gurugram', 'baroda': 'vadodara', 'poona': 'pune', 'orissa': 'odisha',
  'cawnpore': 'kanpur', 'simla': 'shimla', 'gauhati': 'guwahati', 'vizag': 'visakhapatnam', 'waltair': 'visakhapatnam', 'faizabad': 'ayodhya'}
def norm(s):
    s = s.lower()
    s = re.sub(r'\(.*?\)', ' ', s)
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    return ' '.join(RENAMES.get(w, w) for w in s.split()) + ' '
def compact(s): return norm(s).replace(' ', '')

# Specific title alias: the Bijapur citadel/Arkilla and Malik-e-Maidan are covered by this fort article.
PLACE_ALIASES = {'vijayapuracitadelmalikemaidan': ['Bijapur Fort']}

# Known same-name search results that are not the listed attraction itself.
# Keep these places in the manual-review queue instead of publishing misleading facts/photos.
MANUAL_ARTICLE_EXCLUSIONS = {
    'andhra-pradesh:112': 'Bheemili Beach article does not describe the Vizag–Bheemili scenic road',
    'andhra-pradesh:17': 'Dolphin’s Nose article does not verify the combined Yarada Beach destination',
    'andhra-pradesh:23': 'Araku Valley article is not an article about the Araku Tribal Museum',
    'andhra-pradesh:41': 'Uppada village article describes the sari and fishing locality, not Uppada Beach',
    'andhra-pradesh:48': 'Bhavani Island article does not verify the combined Prakasam Barrage destination',
    'andhra-pradesh:58': 'Pedana municipality article does not verify the listed Kalamkari craft destination',
    'andhra-pradesh:51': 'Mangalagiri–Tadepalli municipal corporation article does not verify the Mangalagiri temple or handloom destination',
    'andhra-pradesh:59': 'Machilipatnam city article does not verify the combined Machilipatnam and Manginapudi Beach destination',
    'andhra-pradesh:65': 'Udayagiri town article does not verify Udayagiri Fort',
    'andhra-pradesh:83': 'Siddavatam village article does not verify Siddavatam Fort',
    'andhra-pradesh:98': 'Penukonda town article does not verify Penukonda Fort',
    'andhra-pradesh:117': 'Appikonda locality article verifies the Someswara temple, not the listed beach',
    'andhra-pradesh:118': 'Pudimadaka village article does not verify Pudimadaka Beach',
    'andhra-pradesh:123': 'Araku Valley article is not an article about the Araku Coffee Museum',
    'andhra-pradesh:133': 'Ainavilli village article does not verify the Siddhi Vinayaka temple',
    'andhra-pradesh:137': 'Dindi search result is a Brazilian song, not the Konaseema backwater destination',
    'andhra-pradesh:138': 'Kadiyam locality article does not verify the Kadiyam nursery belt',
    'andhra-pradesh:152': 'Jaggayyapeta town article does not verify the Buddhist stupa site',
    'andhra-pradesh:153': 'Five Tathagatas article is unrelated to the Dhyana Buddha statue at Amaravati',
    'andhra-pradesh:170': 'Jonnawada village article does not verify the Kamakshi temple itself',
    'andhra-pradesh:176': 'Alipiri neighbourhood article does not verify the Alipiri footpath',
    'andhra-pradesh:182': 'Gudimallam village article does not verify the Parasurameswara temple itself',
    'andhra-pradesh:183': 'Nagalapuram village article does not verify the Vedanarayana temple itself',
    'andhra-pradesh:186': 'Nandalur town article does not verify the listed Soumyanatha temple; its extract instead describes Buddhist remains',
    'andhra-pradesh:193': 'Srisailam town article does not verify Pathala Ganga or the dam',
    'andhra-pradesh:196': 'Hemavathi result is a film, not the Hemavathi temple complex',
    'andhra-pradesh:197': 'Kadiri town article does not verify the Lakshmi Narasimha temple itself',
    'andhra-pradesh:200': 'Rayadurgam town article does not verify the fort itself',
}
def sig(s):
    return {w for w in norm(s).split() if len(w) >= 4 and w not in GENERIC}
def strip_name(n):
    return re.sub(r'\s*\(.*?\)\s*', ' ', n).strip()

def variants(name):
    base = strip_name(name)
    out = [base]
    out.extend(PLACE_ALIASES.get(compact(base), []))
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
    vs = {compact(v) for v in variants(p['name'])}
    if nt in broad and compact(t) not in vs: return False
    # coordinates from Wikipedia, else from Wikidata (many articles, e.g. Jog Falls, only have them there)
    c = (pg.get('coordinates') or [None])[0] or pg.get('_wc')
    loc = sig(p.get('dist', '')) | sig(p.get('st', ''))
    tw, pw = sig(t), sig(p['name']) - loc
    # exact: the page we got by looking up the place's own name (not a redirect into a section),
    # or a title equal to the name allowing for old town names and spacing (Mysore Zoo = Mysuru Zoo, Lal Bagh = Lalbagh)
    exact_title = (exact and not pg.get('_frag')) or compact(t) in vs
    if not exact_title and not (tw & pw): return False
    if c:
        d = km(p['ll'], (c['lat'], c['lon']))
        return d <= (25 if exact_title else 15)
    return exact_title and exact and bool(pw)  # no coordinates anywhere: only an exact, distinctive title

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

def wdc(pages):
    """Fill pg['_wc'] from Wikidata P625 for pages without Wikipedia coordinates."""
    need = {}
    for pg in pages:
        q = (pg.get('pageprops') or {}).get('wikibase_item')
        if q and not pg.get('coordinates') and '_wc' not in pg: need.setdefault(q, []).append(pg)
    ids = sorted(need)
    for i in range(0, len(ids), 50):
        j = get(WD, dict(action='wbgetentities', ids='|'.join(ids[i:i+50]), props='claims'))
        for q, e in (j.get('entities') or {}).items():
            for cl in (e.get('claims') or {}).get('P625', [])[:1]:
                v = ((cl.get('mainsnak') or {}).get('datavalue') or {}).get('value') or {}
                if 'latitude' in v:
                    for pg in need.get(q, []): pg['_wc'] = {'lat': v['latitude'], 'lon': v['longitude']}

def debug(names, places, broad):
    for nm in names:
        for p in [x for x in places if x['name'] == nm][:1]:
            print(f"\n== {p['k']} {p['name']} ({p['dist']}, {p['st']}) at {p['ll']}  sig={sorted(sig(p['name']) - sig(p['dist']) - sig(p['st']))}")
            vs = variants(p['name'])
            j = get(API, dict(PROPS, action='query', redirects='1', titles='|'.join(vs)))
            q = j.get('query', {}); wdc(q.get('pages', {}).values()); print('  normalized/redirects:', q.get('normalized'), q.get('redirects'), ' continue:', j.get('continue'))
            for pg in q.get('pages', {}).values():
                c = (pg.get('coordinates') or [None])[0] or pg.get('_wc')
                print(f"  title-page {pg.get('title')!r} missing={'missing' in pg} coords={c and (c['lat'], c['lon'])} props={list((pg.get('pageprops') or {}).keys())} -> good={good(pg, p, True, broad)}")
            b = strip_name(p['name'])
            for qs in (f"{b} {p['dist']}", b):
                j = get(API, dict(PROPS, action='query', generator='search', gsrlimit='6', gsrnamespace='0', gsrsearch=qs))
                cs = sorted(j.get('query', {}).get('pages', {}).values(), key=lambda g: g.get('index', 9)); wdc(cs)
                for pg in cs:
                    c = (pg.get('coordinates') or [None])[0] or pg.get('_wc')
                    print(f"  search[{qs}] {pg.get('title')!r} coords={c and (round(c['lat'],3), round(c['lon'],3))} d={c and round(km(p['ll'], (c['lat'], c['lon'])),1)} -> good={good(pg, p, False, broad)}")

def main():
    states = {s['slug']: s['name'] for s in json.load(open(os.path.join(ROOT, 'data', 'states.json')))}
    places = []
    broad = {norm(n).strip() for n in states.values()} | {'india'}
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'places', '*.json'))):
        slug = os.path.basename(f)[:-5]
        if FACTS_STATE and slug != FACTS_STATE: continue
        for p in json.load(open(f))['places']:
            places.append(dict(k=f"{slug}:{p['n']}", slug=slug, n=p['n'], name=p['name'], dist=p.get('district', ''),
                               st=states.get(slug, ''), cat=p.get('category', ''), ll=(p['lat'], p['lng'])))
            broad.add(norm(p.get('district', '')).strip()); broad.add(norm(p.get('district', '') + ' district').strip())
    if os.environ.get('FACTS_DEBUG'):
        debug(os.environ['FACTS_DEBUG'].split('|'), places, broad); return
    legacy = os.path.join(ROOT, '.github', 'facts-state.json')
    seed = STATE if os.path.exists(STATE) else legacy
    old = json.load(open(seed)) if os.path.exists(seed) else {}
    prefix = FACTS_STATE + ':' if FACTS_STATE else None
    def scoped(d): return {k: v for k, v in d.items() if k.startswith(prefix)} if prefix else d
    R = scoped(old.get('r', {})); M = scoped(old.get('m', {})); H = scoped(old.get('h', {})); PEND = scoped(old.get('p', {})); M2 = set(scoped({k: True for k in old.get('m2', [])}))
    if FACTS_STATE: os.makedirs(os.path.dirname(STATE), exist_ok=True)
    # Enforce manual exclusions against previously published matches as well as new search results.
    # Without this purge, an old false-positive can survive indefinitely when its match fingerprint is unchanged.
    for k in MANUAL_ARTICLE_EXCLUSIONS:
        if k in R:
            R.pop(k, None); M[k] = NOW; M2.add(k)
    fp = lambda p: hashlib.md5(f"{p['name']}|{p['ll'][0]:.3f}|{p['ll'][1]:.3f}".encode()).hexdigest()[:10]
    keys = {p['k'] for p in places}
    R = {k: v for k, v in R.items() if k in keys}; M = {k: v for k, v in M.items() if k in keys}
    MV = 4  # matching rules version; re-check previous results after adding the explicit Bijapur article alias
    if old.get('m2v') != MV: M2 = set()  # misses from older rules get another look too
    todo = [p for p in places if FORCE or (p['k'] in R and R[p['k']].get('mv', 1) < MV) or (p['k'] in M and p['k'] not in M2) or H.get(p['k']) != fp(p) or (p['k'] in M and NOW - M[p['k']] > 60*DAY)
            or (p['k'] in R and NOW - R[p['k']].get('at', 0) > 60*DAY) or (p['k'] not in R and p['k'] not in M)]
    hit = {k: v for k, v in PEND.items() if k in keys}
    todo = [p for p in todo if p['k'] not in hit]
    print(f'{len(places)} places, {len(todo)} to check, {len(hit)} matched earlier and waiting for details', flush=True)
    KEEP = ('title', 'fullurl', 'pageprops', 'thumbnail', 'pageimage', 'coordinates', '_wc')
    def checkpoint():
        pend = {k: {x: pg[x] for x in KEEP if x in pg} for k, pg in hit.items() if k not in R or R[k].get('osm') or R[k].get('mv', 1) < MV}
        json.dump({'v': 1, 'r': R, 'm': M, 'h': H, 'p': pend, 'm2': sorted(M2 & set(M)), 'm2v': MV}, open(STATE, 'w'), ensure_ascii=False, separators=(',', ':'))
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
        wdc(pages.values())
        for r_ in q.get('redirects', []):  # a redirect to a section of a bigger article is not the place's own article
            if r_.get('tofragment') and r_['to'] in pages: pages[r_['to']] = dict(pages[r_['to']], _frag=1)
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
            cands = sorted(j.get('query', {}).get('pages', {}).values(), key=lambda g: g.get('index', 9)); wdc(cands)
            for pg in cands:
                if good(pg, p, False, broad): got = pg; break
            if got: break
        if not got:
            j = get(API, dict(PROPS, action='query', generator='geosearch', ggscoord=f"{p['ll'][0]}|{p['ll'][1]}", ggsradius='2000', ggslimit='15'))
            for pg in j.get('query', {}).get('pages', {}).values():
                if good(pg, p, False, broad): got = pg; break
        if got: hit[p['k']] = got
        else:
            o = osm(p)
            if o: R[p['k']] = dict(o, at=NOW, mv=MV); M.pop(p['k'], None)
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
        if k in MANUAL_ARTICLE_EXCLUSIONS:
            M[k] = NOW; M2.add(k); R.pop(k, None)
            continue
        q = (pg.get('pageprops') or {}).get('wikibase_item'); c = claims.get(q, {})
        r = {'w': pg['title'], 'u': pg.get('fullurl', ''), 'x': ext.get(pg['title'], ''), 'q': q or '', 'at': NOW, 'mv': MV}
        co = (pg.get('coordinates') or [None])[0] or pg.get('_wc')
        if co: r['ll'] = [round(co['lat'], 4), round(co['lon'], 4)]  # the article's own point, used to correct the atlas position
        web = [v for v in vals(c, 'P856') if isinstance(v, str)]
        if web: r['web'] = web[0]
        her = [labels.get(v['id'], '') for v in vals(c, 'P1435') if isinstance(v, dict)]
        her = [h for h in her if h]
        if her: r['her'] = sorted(set(her))[:3]
        el = [v for v in vals(c, 'P2044') if isinstance(v, dict) and 'amount' in v]
        if el:
            try: r['el'] = round(float(el[0]['amount']) * (0.3048 if str(el[0].get('unit', '')).endswith('Q3710') else 1))  # Q3710 = foot
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
    if not FACTS_STATE:
        unv = [{'k': p['k'], 'name': p['name'], 'district': p['dist'], 'state': p['st'], 'category': p['cat']} for p in places if p['k'] not in R]
        json.dump(unv, open(os.path.join(OUTD, '_unverified.json'), 'w'), ensure_ascii=False, indent=0)
    json.dump({'v': 1, 'r': R, 'm': M, 'h': H, 'p': {}, 'm2': sorted(M2 & set(M)), 'm2v': MV}, open(STATE, 'w'), ensure_ascii=False, separators=(',', ':'))
    unverified_count = sum(1 for p in places if p['k'] not in R)
    print(f'done: {len(R)} verified, {unverified_count} unverified', flush=True)

if __name__ == '__main__':
    main()
