"""Use the photo of each place's verified Wikipedia article (from data/facts) in data/photos.json.

The older photo job matched loosely (any article within 50 km), so a few cards showed the wrong place.
A verified article's lead image is retained only after Commons confirms the file, raster dimensions and free-use licence.
Author and licence metadata are stored with every published image."""
import json, os, glob, re, urllib.parse, urllib.request, html, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'data', 'photos.json'); CRED = os.path.join(ROOT, 'data', 'photo-credits.json')
ph = json.load(open(OUT)); base = ph['base']
old_cred = json.load(open(CRED)) if os.path.exists(CRED) else {}
P, cred = {}, {}
all_keys = set()
UA = 'IndiaTravelAtlas/1.0 (https://pyhrishi.github.io/india-travel-atlas/; github.com/pyhrishi)'
def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', value or ''))).strip()[:160]
def commons_info(files):
    """Confirm each Commons file exists, is a real raster image, and exposes free-use licence metadata."""
    out, failed = {}, set()
    for i in range(0, len(files), 50):
        batch = files[i:i+50]
        titles = '|'.join('File:' + name for name in batch)
        params = urllib.parse.urlencode({
            'action': 'query', 'format': 'json', 'maxlag': '5', 'prop': 'imageinfo',
            'iiprop': 'extmetadata|mime|size',
            'iiextmetadatafilter': 'Artist|LicenseShortName|LicenseUrl',
            'titles': titles
        })
        req = urllib.request.Request('https://commons.wikimedia.org/w/api.php?' + params,
                                     headers={'User-Agent': UA})
        data = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=45) as response:
                    data = json.load(response)
                if data.get('error'):
                    raise RuntimeError(data['error'].get('code', 'Commons API error'))
                break
            except Exception as error:
                if attempt == 3:
                    failed.update(batch)
                    print(f'Commons metadata unavailable for batch {i//50 + 1}: {error}', flush=True)
                    data = {}
                else:
                    time.sleep(2 * (attempt + 1))
        time.sleep(0.2)
        for page in (data.get('query') or {}).get('pages', {}).values():
            info = (page.get('imageinfo') or [{}])[0]
            ext = info.get('extmetadata') or {}
            mime = info.get('mime', '')
            width, height = info.get('width', 0), info.get('height', 0)
            license_name = clean((ext.get('LicenseShortName') or {}).get('value', ''))
            if not mime.startswith('image/') or mime == 'image/svg+xml' or width < 300 or height < 200 or not license_name:
                continue
            filename = page.get('title', '').removeprefix('File:').replace(' ', '_')
            out[filename] = {
                'a': clean((ext.get('Artist') or {}).get('value', '')),
                'l': license_name,
                'lu': clean((ext.get('LicenseUrl') or {}).get('value', ''))
            }
    return out, failed
for pf in sorted(glob.glob(os.path.join(ROOT, 'data', 'places', '*.json'))):
    slug = os.path.basename(pf)[:-5]
    for place in json.load(open(pf))['places']:
        all_keys.add(f"{slug}:{place['n']}")
def rel(u):
    u = u.split('?')[0].replace('https://thumb.wikimedia.org/', 'https://upload.wikimedia.org/')
    u = re.sub(r'/(\d+)px-', '/1600px-', u)
    return u[len(base):] if u.startswith(base) else u
candidates = []
rejected = 0
# Manually audited article lead images that depict a different subject/context.
# Keep these places on the illustrated fallback until a place-specific photo is verified.
MANUAL_PHOTO_EXCLUSIONS = {
    'andhra-pradesh:16': 'underway submarine image, not the beachside museum',
    'andhra-pradesh:17': 'RK Beach sunset image, not Dolphin Nose or Yarada',
    'andhra-pradesh:20': 'banana fields image, not Etikoppaka lacquer toys',
    'andhra-pradesh:23': 'Araku Valley landscape image, not the Tribal Museum',
    'andhra-pradesh:37': 'train entering Pithapuram station, not the town temples',
    'andhra-pradesh:40': 'satellite image rather than a visitor photograph of Hope Island',
    'andhra-pradesh:41': 'Vakalpudi shore image, not Uppada Beach',
    'andhra-pradesh:52': 'British Museum collection image, not the Amaravati site or museum',
    'andhra-pradesh:51': 'generic Mangalagiri town image, not the Panakala Narasimha temple or handloom craft',
    'andhra-pradesh:57': 'performer portrait, not a photograph of Kuchipudi village',
    'andhra-pradesh:59': 'town-square photograph, not Manginapudi Beach or a representative beach view',
    'andhra-pradesh:79': 'generic railway landscape, not Koundinya Wildlife Sanctuary',
    'andhra-pradesh:91': 'blackbuck photograph, not the Great Indian Bustard sanctuary',
    'andhra-pradesh:106': 'canal aerial view, not a clear photograph of Thotapalli Barrage',
    'andhra-pradesh:117': 'Appikonda hillock view, not the listed beach',
    'andhra-pradesh:112': 'Gosthani river image, not the Vizag–Bheemili coastal road',
    'andhra-pradesh:123': 'Araku Valley landscape, not the Coffee Museum',
    'andhra-pradesh:138': 'Kadiyam railway station sign, not the nursery belt',
    'andhra-pradesh:153': 'Chinese temple Five Tathagatas image, unrelated to the Amaravati Dhyana Buddha',
    'andhra-pradesh:154': 'bank and residential area image, not the Dharanikota heritage site',
    'andhra-pradesh:163': 'festival idols from a different temple, not Mopidevi Subrahmanya shrine',
    'andhra-pradesh:176': 'generic Tirupati image, not the Alipiri footpath',
    'andhra-pradesh:182': 'village farmland image, not the Gudimallam temple',
    'andhra-pradesh:183': 'hill-stream landscape, not the Vedanarayana Temple',
    'andhra-pradesh:193': 'general Srisailam town image, not Pathala Ganga or the dam',
}
for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'facts', '*.json'))):
    slug = os.path.basename(f)[:-5]
    if slug.startswith('_'): continue
    for n, r in json.load(open(f)).items():
        if not r.get('img') or not r.get('w') or not r.get('file'): continue
        k = f'{slug}:{n}'
        if k in MANUAL_PHOTO_EXCLUSIONS:
            rejected += 1
            continue
        fn = (r.get('file') or '').lower()
        if re.search(r'\.svg|\bmap\b|_map|map_|locator|location|flag|logo|emblem|seal|coat_of_arms|diagram|plan_of|bust|portrait', fn):
            rejected += 1
            continue
        new = rel(r['img'])
        if not new or (new.startswith('http') and 'upload.wikimedia.org' not in new):
            rejected += 1
            continue
        candidates.append((k, new, r['file'], r['w']))
file_meta, failed_files = commons_info(sorted({x[2] for x in candidates}))
changed = added = same = 0
for k, new, filename, title in candidates:
    meta = file_meta.get(filename.replace(' ', '_'))
    if not meta:
        prev = old_cred.get(k, {})
        if filename in failed_files and prev.get('f') == filename and prev.get('l'):
            meta = {x: prev[x] for x in ('a', 'l', 'lu') if prev.get(x)}
        else:
            rejected += 1
            continue
    P[k] = new
    cred[k] = {'f': filename, 'w': title, **meta}
    prev = old_cred.get(k, {})
    if prev.get('f') == filename: same += 1
    elif prev: changed += 1
    else: added += 1
# Fail closed on Commons API outages. Do not publish a partial photo map;
# the workflow retries this step and preserves the previously committed photo data.
if failed_files:
    raise SystemExit(f"Commons verification incomplete for {len(failed_files)} files; refusing to write partial photo outputs.")

# A photo is published only when it is the lead image of that place's own verified article.
# Unverified places deliberately show the illustrated fallback rather than a nearby/wrong photo.
ph['p'] = dict(sorted(P.items()))
ph['miss'] = sorted(all_keys - set(P))
ph['updated'] = int(time.time())
json.dump(ph, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump(dict(sorted(cred.items())), open(CRED, 'w'), ensure_ascii=False, separators=(',', ':'))

print(f'verified-article photos: {same} retained, {changed} replaced, {added} added, {rejected} non-photo assets rejected; {len(P)} of {len(all_keys)} places have verified photos; {len(all_keys - set(P))} intentionally have no verified photo')
