"""Recompute the service-worker cache version in sw.js after changing index.html or data files,
so installed copies pick up the new files for offline use. Run from anywhere."""
import os, re, json, hashlib
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sw = open('sw.js').read()
files = json.loads(re.search(r'CORE=(\[.*?\]);', sw).group(1))
import glob
fixed = [f for f in files if not f.startswith('data/')]
files = fixed + sorted(f for f in glob.glob('data/**/*.json', recursive=True))
ver = hashlib.sha1(b''.join(open(f, 'rb').read() for f in files if f != './')).hexdigest()[:10]
sw = re.sub(r'const V="ita-[0-9a-f]+",CORE=\[.*?\];', f'const V="ita-{ver}",CORE={json.dumps(files)};', sw, count=1)
open('sw.js', 'w').write(sw)
print('sw version', ver, 'files', len(files))
