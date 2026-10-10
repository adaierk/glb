"""Recover v17 evidence and package exact tested source on the existing CI host."""
import hashlib, json, os, re, subprocess, urllib.request, urllib.error, zipfile
from pathlib import Path
from PIL import Image
ROOT=Path.cwd(); META=ROOT/'toeo-recovery/v17'; WORK=Path(os.environ['RUNNER_TEMP'])/'v17-release'
WORK.mkdir(parents=True,exist_ok=True)
RUN=38017513763; ARTIFACT=11657535463
ARTIFACT_SHA='2aa2cd5bbc42fad762b9f8260a2256a5c7547ae95ab825e6515d541ffe779775'
EXE_SHA='635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'
def sha(data):return hashlib.sha256(data).hexdigest()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**kw):return None
req=urllib.request.Request(f'https://api.github.com/repos/adaierk/glb/actions/artifacts/{ARTIFACT}/zip',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'User-Agent':'TOEO-v17-release','Accept':'application/vnd.github+json'})
try:
 response=urllib.request.build_opener(NoRedirect()).open(req,timeout=90)
 data=response.read()
except urllib.error.HTTPError as e:
 if e.code not in (301,302,303,307,308):raise
 target=e.headers['Location']
 # Do not forward repository credentials to the signed storage URL.
 data=urllib.request.urlopen(urllib.request.Request(target,headers={'User-Agent':'TOEO-v17-release'}),timeout=120).read()
assert sha(data)==ARTIFACT_SHA,'Native artifact SHA mismatch'
archive=WORK/'native.zip';archive.write_bytes(data)
z=zipfile.ZipFile(archive);assert z.testzip() is None
first=json.loads(z.read('first/runtime_result.json'));second=json.loads(z.read('reentered/runtime_result.json'))
for result in (first,second):
 assert result['map_entered'] and result['equipment_matches_database_native'] and result['equipment_hp_bonus_native'] and result['hp_gauge_draw_succeeded_native']
 assert result['saved_inventory']['money']==5000 and result['saved_inventory']['items']==[]
 assert [x['slot'] for x in result['saved_inventory']['equipment']]==[1,2]
 assert result['saved_vitals']=={'hp':100,'tp':30,'max_hp':110,'max_tp':30}
 assert {x['slot']:x['icon_id'] for x in result['native_equipment_samples'][-1]['order']}=={1:1,2:857}
assert first['equip_request_native'] and first['unequip_request_native'] and second['position_restored_without_movement']
assert first['saved_inventory']==second['saved_inventory']
states=[tuple(x['slot'] for x in e['order']) for e in first['native_equipment_samples']]
pos=-1
for expected in [(1,),(1,2),(2,),(1,2)]:pos=states.index(expected,pos+1)
events=[json.loads(x) for x in z.read('first/server.jsonl').decode().splitlines()]
moves=[x for x in events if x.get('event')=='item_move_committed']
assert not any(x.get('event')=='item_move_rejected' for x in events)
assert [(x['source_location'],x['destination_location']) for x in moves]==[(2,4),(2,4),(4,2),(2,4)]
assert all(x['snapshot']['money']==5000 for x in moves)
mapping=json.loads((META/'source_map.json').read_text())
source=WORK/'source/toeo-tests';source.mkdir(parents=True,exist_ok=True)
files={};rows=[]
for row in mapping['files']:
 body=(ROOT/row['git_path']).read_bytes()
 blob=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
 assert blob==row['expected_git_blob'],row['git_path']
 (source/row['local']).write_bytes(body);files['toeo-tests/'+row['local']]=body
 rows.append({**row,'git_blob':blob,'sha256':sha(body),'matched':True})
assert len(rows)==116
test=subprocess.run(['python','-m','unittest','discover','-s',str(source)],cwd=source,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(META/'unit_tests.txt').write_text(test.stdout)
assert test.returncode==0,test.stdout
count=int(re.search(r'Ran (\d+) tests?',test.stdout).group(1));assert count==61
images=[]
for entry in [('first/original_desktop_170s.png','TOEO_Rashuan_Equipment_20261010_v17.png'),('first/original_desktop_180s.png','TOEO_Rashuan_Unequip_20261010_v17.png'),('reentered/original_desktop_150s.png','TOEO_Rashuan_Equipment_Restored_20261010_v17.png'),('first/original_desktop_230s.png','TOEO_Rashuan_Map_20261010_v17.png')]:
 raw=z.read(entry[0]);rawpath=WORK/Path(entry[0]).name;rawpath.write_bytes(raw)
 image=Image.open(rawpath);assert image.width>=808 and image.height>=632
 crop=image.crop((8,32,808,632));dest=META/entry[1];crop.save(dest)
 assert Image.open(dest).tobytes()==crop.tobytes()
 images.append({'file':entry[1],'source':entry[0],'source_sha256':sha(raw),'sha256':sha(dest.read_bytes()),'crop':[8,32,808,632],'alterations':'Desktop crop only; original game pixels unchanged'})
proof={'version':'v17','passed':True,'visual_reviewed':False,'tested_commit':mapping['tested_commit'],'windows_run_id':RUN,'artifact_id':ARTIFACT,'artifact_sha256':ARTIFACT_SHA,'original_exe_sha256':EXE_SHA,'native_equipment_transitions':states,'native_move_counts':[x['count'] for x in moves],'native_equip_unequip_reequip_verified':True,'same_instances_restored_after_restart':True,'native_icon_ids':{'weapon':1,'body':857},'native_hp':100,'native_max_hp':110,'native_tp':30,'local_checks_passed':61,'source_files_verified':116,'equipment_fixture_provenance':'Explicit Local Test Sword / Local Test Body, provisional local maxHP+10; official item masters unresolved','appearance_restored':False,'native_exceptions':{'first':len(first.get('native_exceptions',[])),'reentered':len(second.get('native_exceptions',[]))},'limitations':['Official gear stats, job/level rules and starter gear unresolved','Equipment world/battle appearance pending','Occupied gear replacement and full combat pending','Complete maps/NPCs/main and side quests/level progression pending','Other caught original native exceptions remain']}
review=META/'visual_review.json'
if review.exists():
 reviewed=json.loads(review.read_text())
 assert reviewed['approved'] is True and reviewed['artifact_sha256']==ARTIFACT_SHA
 assert reviewed['images_sha256']=={x['file']:x['sha256'] for x in images}
 proof['visual_reviewed']=True
(META/'v17_milestone.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2))
consistency={'passed':True,'commit':mapping['tested_commit'],'count':116,'files':rows}
(META/'source_consistency.json').write_text(json.dumps(consistency,indent=2))
(META/'images.json').write_text(json.dumps(images,indent=2))
for phase,result in [('first',first),('reentered',second)]:
 (META/(phase+'_runtime_result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
if not proof['visual_reviewed']:
 print('NATIVE_PROOF_AND_IMAGES_READY; visual review required before ZIP seal')
 raise SystemExit(0)
for name in ('Run_TOEO_Local.cmd','Run_TOEO_Rashuan.cmd','Prepare_TOEO_Client.cmd'):
 files[name]=(ROOT/name).read_bytes()
cmd=files['Run_TOEO_Rashuan.cmd'].decode().replace('--world-profile rashuan','--world-profile rashuan --equipment-preview')
files['Run_TOEO_Equipment_Test.cmd']=cmd.replace('\r\n','\n').replace('\n','\r\n').encode()
files['requirements_native.txt']=b'frida\npillow\n'
files['README_CN.txt']=(META/'README_CN.txt').read_bytes()
files['NEXT_RECOVERY_V17.txt']=(META/'NEXT_RECOVERY_V17.txt').read_bytes()
files['TOEO_RESTORATION_CURRENT_STATE.txt']=('v17: native equip / unequip / re-equip and restart verified. Official gear masters / appearance / complete gameplay pending.\nNative run '+str(RUN)+'; original EXE unchanged.\n').encode()
for name in ('v17_milestone.json','source_consistency.json','images.json','unit_tests.txt','first_runtime_result.json','reentered_runtime_result.json','visual_review.json'):
 files['evidence/v17/'+name]=(META/name).read_bytes()
for phase,seconds in [('first',(140,160,170,180,190,200,225,230)),('reentered',(140,150))]:
 for name in ('runtime.jsonl','server.jsonl','runtime_result.json','screenshots.json','graphics_assets_manifest.json'):
  path=phase+'/'+name
  if path in z.namelist():files[f'evidence/windows_run{RUN}/'+path]=z.read(path)
 for second in seconds:
  path=f'{phase}/original_desktop_{second:03d}s.png'
  if path in z.namelist():files[f'evidence/windows_run{RUN}/'+path]=z.read(path)
for row in images:files['evidence/'+row['file']]=(META/row['file']).read_bytes()
files['research/build_release_ci.py']=(META/'build_release_ci.py').read_bytes()
metadata={'version':'v17','tested_commit':mapping['tested_commit'],'checkpoint_commit':os.environ['GITHUB_SHA'],'windows_run_id':RUN,'artifact_id':ARTIFACT,'windows_artifact_sha256':ARTIFACT_SHA,'local_checks_passed':61,'source_files_verified':116,'native_equipment_equip_unequip_restart_verified':True,'equipment_data_provenance':proof['equipment_fixture_provenance'],'appearance_restored':False,'complete_gameplay':False,'original_assets_included':False,'user_database_included':False,'limitations':proof['limitations'],'images':images,'files_sha256':{name:sha(body) for name,body in sorted(files.items())}}
files['RELEASE_METADATA.json']=json.dumps(metadata,ensure_ascii=False,indent=2).encode()
dest=META/'TOEO_Local_World_Recovery_20261010_v17.zip';prefix='TOEO_Local_World_v17/'
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as release:
 for name,body in sorted(files.items()):release.writestr(prefix+name,body)
with zipfile.ZipFile(dest) as release:
 assert release.testzip() is None and all(release.read(prefix+name)==body for name,body in files.items())
 assert not any('.sqlite' in n or '__pycache__' in n or 'userdata/' in n for n in release.namelist())
manifest={'version':'v17','sha256':sha(dest.read_bytes()),'bytes':dest.stat().st_size,'entries':len(files),'crc_check':'PASS','archive_source_consistency':'PASS','user_database_included':False,'checkpoint_commit':os.environ['GITHUB_SHA'],'windows_run_id':RUN,'windows_tested_commit':mapping['tested_commit'],'windows_artifact_id':ARTIFACT,'windows_artifact_sha256':ARTIFACT_SHA,'local_checks_passed':61,'source_files_verified':116,'images':images}
(META/'MANIFEST_V17_SEALED.json').write_text(json.dumps(manifest,indent=2))
print('V17_RELEASE_SEALED',json.dumps({k:v for k,v in manifest.items() if k!='images'}))
