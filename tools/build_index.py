import json,glob,re,os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
R={
 'unesco':r'UNESCO','jyotirlinga':r'Jyotirling','shakti':r'Shakti Peeth','stepwell':r'stepwell|baori|bawdi|\bvav\b',
 'tea':r'tea estate|tea garden|tea gardens|tea hills|coffee estate|coffee country|plantation',
 'tiger':r'\btiger','monastery':r'monaster|gompa','palace':r'palace','fort':r'\bfort\b',
}
HIM={'uttarakhand','himachal-pradesh','jammu-and-kashmir','ladakh','sikkim','arunachal-pradesh','west-bengal'}
PERMIT=re.compile(r'permit|\bILP\b|\bPAP\b|restricted',re.I)
ADV=re.compile(r'check before|closed after|check if open|check open spots|road status|advisory|subsidence',re.I)
out={}
for s in json.load(open('data/states.json')):
  d=json.load(open(f"data/places/{s['slug']}.json"))
  rows=[]
  for p in d['places']:
    t=p['name']+' '+p['category']+' '+p['why']
    tags=[k for k,rx in R.items() if re.search(rx,t,re.I)]
    if p['g']=='water' and re.search(r'waterfall|falls',p['name']+' '+p['category'],re.I): tags.append('falls')
    if p['g']=='coast' and re.search(r'beach',t,re.I): tags.append('beach')
    if re.search(r'hill station',p['category']+' '+p['why'],re.I): tags.append('hillstn')
    if PERMIT.search(p['why']): tags.append('permit')
    if ADV.search(p['why']): tags.append('adv')
    t=p.get('trek')
    if t:
      k=t.get('kind','')
      tags.append('peak' if k=='Peak' else 'trek')
      if k=='Pass': tags.append('pass')
      if k=='Summit trek': tags.append('summit')
      if t.get('diff')=='Easy' and k!='Peak': tags.append('easy')
      if k in ('Trek','Summit trek','Pass') and s['slug'] in HIM: tags.append('himtrek')
      if t.get('permit') and 'permit' not in tags: tags.append('permit')
    k=p.get('park')
    if k:
      tags.append('park')
      if k.get('kind')=='Tiger reserve': tags.append('tigerres')
      if k.get('kind')=='Marine park': tags.append('marine')
      if k.get('safari'): tags.append('safari')
    for f in ('wet','bird','cave','sky','rail','drive','gi','art','eat','beach','fall','fort','wild','stay'):
      if p.get(f): tags.append(f)
    if p.get('wet',{}).get('ramsar'): tags.append('ramsar')
    for c in p.get('circ',[]): tags.append('c-'+c)
    for k in p.get('stay',{}).get('kinds',[]):
      kl=k.lower()
      for t,w in (('st-house','houseboat'),('st-mon','monastery'),('st-home','homestay'),('st-forest','forest'),('st-forest','jungle lodge'),('st-camp','camp')):
        if w in kl and t not in tags: tags.append(t)
    for x in p.get('wild',{}).get('sp',[]): tags.append('sp-'+x)
    if p.get('fort',{}).get('kind')=='Stepwell' or p['category']=='Stepwell': tags.append('stepwell')
    if p.get('fort',{}).get('unesco'): tags.append('unescofort')
    rows.append([p['n'],p['name'],p['district'],p['category'],p['g'],round(p['lat'],4),round(p['lng'],4),p['tier'],p['months'][0],p['months'][1],p['time'],' '.join(tags)])
  out[s['slug']]={'intro':d['intro'],'bases':d['bases'],'trails':d['trails'],'festivals':d.get('festivals',[]),'p':rows}
json.dump(out,open('data/index.json','w'),ensure_ascii=False,separators=(',',':'))
print(os.path.getsize('data/index.json'))
from collections import Counter
print(Counter(t for v in out.values() for r in v['p'] for t in r[11].split()))
