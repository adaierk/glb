"""Preserve real Windows native observations; never manufacture game images."""
import hashlib,io,json,os,re,urllib.request,urllib.error,zipfile
from pathlib import Path
from PIL import Image
ROOT=Path.cwd();config=json.loads((ROOT/'toeo-recovery/v19/capture_config.json').read_text())
OUT=ROOT/'toeo-recovery/v19/evidence'/str(config['run']);OUT.mkdir(parents=True,exist_ok=True)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'User-Agent':'TOEO-native-evidence','Accept':'application/vnd.github+json'}
def api(path):
 return json.loads(urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/adaierk/glb/'+path,headers=headers),timeout=60).read())
artifacts=api('actions/runs/'+str(config['run'])+'/artifacts')['artifacts']
a=next(x for x in artifacts if x['name']=='toeo-v19-native-encounter')
request=urllib.request.Request(a['archive_download_url'],headers=headers)
try:data=urllib.request.build_opener(NoRedirect()).open(request,timeout=90).read()
except urllib.error.HTTPError as e:
 if e.code not in (301,302,303,307,308):raise
 data=urllib.request.urlopen(urllib.request.Request(e.headers['Location'],headers={'User-Agent':'TOEO-native-evidence'}),timeout=120).read()
digest=hashlib.sha256(data).hexdigest()
assert 'sha256:'+digest==a['digest']
z=zipfile.ZipFile(io.BytesIO(data));assert z.testzip() is None
(OUT/'artifact.json').write_text(json.dumps({'run':config['run'],'artifact':a['id'],'sha256':digest,'tested_commit':a['workflow_run']['head_sha'],'image_transform':'Exact 800x600 crop (8,32,808,632); no retouching'},indent=2))
for n in ['first/runtime_result.json','first/server.jsonl']:
 (OUT/Path(n).name).write_bytes(z.read(n))
events=[json.loads(line) for line in z.read('first/runtime.jsonl').decode().splitlines() if line.strip()]
names=('enemy','battle','pick','target','npc','command','network','model','action')
kept=[e for e in events if any(n in str(e.get('event','')).lower() for n in names)]
counts={}
for e in events:counts[e.get('event','?')]=counts.get(e.get('event','?'),0)+1
(OUT/'event_counts.json').write_text(json.dumps(counts,indent=2))
(OUT/'native_events.json').write_text(json.dumps(kept,indent=2))
screens=[n for n in z.namelist() if re.fullmatch(r'first/original_desktop_\d+s.png',n) and int(re.search(r'_(\d+)s',n).group(1))>=140]
for n in screens:
 im=Image.open(io.BytesIO(z.read(n)));assert im.size[0]>=808 and im.size[1]>=632
 im.crop((8,32,808,632)).save(OUT/Path(n).name)
print(json.dumps({'artifact':a['id'],'events':len(events),'preserved':len(kept),'screenshots':screens,'result':json.loads(z.read('first/runtime_result.json'))},ensure_ascii=False))
