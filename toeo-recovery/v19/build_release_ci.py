"""Seal v19 only from exact native-tested source and visually reviewed original pixels."""
import hashlib,json,os,re,subprocess,zipfile
from pathlib import Path
ROOT=Path.cwd();META=ROOT/'toeo-recovery/v19'
config=json.loads((META/'release_config.json').read_text())
RUN=config['run'];TESTED=config['tested_commit']
EVIDENCE=META/'evidence'/str(RUN)
proof=json.loads((EVIDENCE/'artifact.json').read_text())
result=json.loads((EVIDENCE/'runtime_result.json').read_text())
assert proof['tested_commit']==TESTED
assert all(result.get(k) for k in ('map_entered','enemy_created_native','enemy_component_native','enemy_world_model_native','enemy_field_symbol_native','enemy_mouse_pick_native','enemy_target_selected_native'))
review=json.loads((META/'visual_review.json').read_text())
assert review['approved'] and review['run']==RUN and review['artifact_sha256']==proof['sha256']
def sha(b):return hashlib.sha256(b).hexdigest()
def source_at(path):
 return subprocess.check_output(['git','show',TESTED+':'+path])
mapping=json.loads((ROOT/'toeo-recovery/v18/source_map.json').read_text())
rows=[{'local':r['local'],'git_path':r['git_path']} for r in mapping['files']]
for name in ('world_enemy_packets.py','world_combat_packets.py','combat_runtime.js','combat_ci_acceptance.py','emulate_enemy.py','emulate_combat.py'):
 rows.append({'local':name,'git_path':'toeo-tests/'+name})
assert len({r['local'] for r in rows})==len(rows)==124
work=Path(os.environ['RUNNER_TEMP'])/'TOEO_V19_RELEASE';source=work/'toeo-tests';source.mkdir(parents=True,exist_ok=True)
files={}
for row in rows:
 body=source_at(row['git_path'])
 blob=hashlib.sha1(b'blob '+str(len(body)).encode()+bytes(1)+body).hexdigest()
 expected=subprocess.check_output(['git','rev-parse',TESTED+':'+row['git_path']],text=True).strip()
 assert blob==expected,row['git_path']
 row.update(git_blob=blob,sha256=sha(body),matched=True)
 (source/row['local']).write_bytes(body)
 files['toeo-tests/'+row['local']]=body
test=subprocess.run(['python','-m','unittest','discover','-s',str(source)],cwd=source,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(META/'unit_tests.txt').write_text(test.stdout)
assert test.returncode==0,test.stdout
unit_count=int(re.search(r'Ran (\d+) tests?',test.stdout).group(1));assert unit_count==61
for name in ('Run_TOEO_Local.cmd','Run_TOEO_Rashuan.cmd','Prepare_TOEO_Client.cmd','Run_TOEO_Encounter_Test.cmd'):
 files[name]=source_at(name)
cmd=files['Run_TOEO_Rashuan.cmd'].decode().replace('--world-profile rashuan','--world-profile rashuan --equipment-preview')
files['Run_TOEO_Equipment_Test.cmd']=cmd.replace('\r\n','\n').replace('\n','\r\n').encode()
files['requirements_native.txt']=b'frida\npillow\n'
files['README_CN.txt']=(META/'README_CN.txt').read_bytes()
files['NEXT_RECOVERY_V19.txt']=(META/'NEXT_RECOVERY_V19.txt').read_bytes()
files['TOEO_RESTORATION_CURRENT_STATE.txt']=(META/'TOEO_RESTORATION_CURRENT_STATE.txt').read_bytes()
for name in ('artifact.json','runtime_result.json','event_counts.json','native_events.json','server.jsonl'):
 files['evidence/v19/'+name]=(EVIDENCE/name).read_bytes()
images=[]
for name,digest in review['images_sha256'].items():
 body=(EVIDENCE/name).read_bytes();assert sha(body)==digest
 files['evidence/v19/'+name]=body
 images.append({'file':name,'sha256':digest,'alterations':'Exact original desktop crop only'})
files['evidence/v19/visual_review.json']=(META/'visual_review.json').read_bytes()
files['evidence/v19/unit_tests.txt']=test.stdout.encode()
consistency={'passed':True,'tested_commit':TESTED,'count':len(rows),'files':rows}
(META/'source_consistency.json').write_text(json.dumps(consistency,indent=2))
files['evidence/v19/source_consistency.json']=json.dumps(consistency,indent=2).encode()
metadata={'version':'v19','tested_commit':TESTED,'windows_run_id':RUN,'windows_artifact':proof['artifact'],
 'windows_artifact_sha256':proof['sha256'],'source_files_verified':len(rows),'local_checks_passed':unit_count,
 'native_map_enemy_verified':True,'native_encounter_entry':config.get('encounter_entry',False),
 'complete_combat':False,'complete_gameplay':False,'original_exe_changed':False,'original_exe_sha256':'635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55',
 'original_assets_included':False,'user_database_included':False,'enemy_provenance':'Explicit local SLIME test; official spawn/stat configuration unresolved',
 'limitations':config['limitations'],'images':images,
 'files_sha256':{n:sha(b) for n,b in sorted(files.items())}}
files['RELEASE_METADATA.json']=json.dumps(metadata,ensure_ascii=False,indent=2).encode()
dest=META/'TOEO_Local_World_Recovery_20261010_v19.zip';prefix='TOEO_Local_World_v19/'
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for n,b in sorted(files.items()):z.writestr(prefix+n,b)
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None and all(z.read(prefix+n)==b for n,b in files.items())
 assert not any('.sqlite' in n or '__pycache__' in n or 'userdata/' in n for n in z.namelist())
manifest={'version':'v19','sha256':sha(dest.read_bytes()),'bytes':dest.stat().st_size,'entries':len(files),
 'crc_check':'PASS','source_consistency':'PASS','tested_commit':TESTED,'windows_run_id':RUN,
 'windows_artifact_sha256':proof['sha256'],'source_files_verified':len(rows),'local_checks_passed':unit_count,
 'complete_combat':False,'images':images,'limitations':config['limitations']}
(META/'MANIFEST_V19_SEALED.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('V19_NATIVE_RELEASE_SEALED',json.dumps(manifest,ensure_ascii=False))
