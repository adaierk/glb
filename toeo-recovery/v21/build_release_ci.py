"""Seal v21 only from exact native-tested source and visually reviewed original pixels."""
import hashlib,io,json,os,re,subprocess,urllib.request,urllib.error,zipfile
from pathlib import Path
ROOT=Path.cwd();META=ROOT/'toeo-recovery/v21'
config=json.loads((META/'release_config.json').read_text())
RUN=config['run'];TESTED=config['tested_commit']
EVIDENCE=META/'evidence'/str(RUN)
proof=json.loads((EVIDENCE/'artifact.json').read_text())
result=json.loads((EVIDENCE/'runtime_result.json').read_text())
assert all(result.get(k) for k in ('battle_pool_started_native','battle_target_selected_native','battle_attack_request_native','battle_attack_command_native','battle_movement_changed_position_native','battle_speed_float_native','battle_attack_program_native','battle_attack_animation_native'))
assert proof['tested_commit']==TESTED
assert all(result.get(k) for k in ('battle_player_body_submitted_native','battle_enemy_body_submitted_native','battle_normal_placement_native'))
assert all(result.get(k) for k in ('map_entered','enemy_created_native','enemy_component_native','enemy_world_model_native','enemy_field_symbol_native','enemy_mouse_pick_native','enemy_target_selected_native'))
if config.get('encounter_entry'):
 assert all(result.get(k) for k in ('encounter_native_confirmed','battle_player_model_native','battle_enemy_model_native','battle_scene_initialized_native','battle_resource_ack_native'))
events=json.loads((EVIDENCE/'native_events.json').read_text())
applied=[e for e in events if e.get('event')=='native_battle_actor_action_applied' and e.get('from_input')==0 and e.get('result')==1 and e.get('identity')==[1,1]]
movement=[e for e in applied if e.get('action',{}).get('command')==1]
attacks=[e for e in applied if e.get('action',{}).get('command')==10004]
assert movement and attacks,'Original B2/5A movement and attack records were not applied'
models={e['identity'][0]:e['model'] for e in events if e.get('event')=='native_battle_render_actor_snapshot' and e.get('phase')=='created'}
assert 1 in models and 0x72000001 in models
attack_animations=[e for e in events if e.get('event')=='native_model_animation_select' and e.get('object')==models[1] and e.get('result')==1 and e.get('args',[0])[0]>=100 and e.get('args',[0])[0] not in (100,101,110) and e.get('host_time',0)>=attacks[0]['host_time']]
assert attack_animations,'Original attack animation was not selected successfully'
action_proof={'passed':True,'tested_commit':TESTED,'run':RUN,'movement_records':movement,'attack_records':attacks,'attack_animations':attack_animations}
action_proof['position_changes']=[e for e in events if e.get('event')=='native_battle_render_actor_snapshot' and e.get('identity')==[1,1] and e.get('phase')=='tick' and abs(e.get('position',[220])[0]-220)>10]
assert action_proof['position_changes']
(META/'action_verification.json').write_text(json.dumps(action_proof,indent=2))
for identity,model in models.items():
 assert any(e.get('event')=='native_model_animation_select' and e.get('object')==model and e.get('result')==1 and e.get('args',[0])[0]==100 for e in events)
 assert any(e.get('event')=='native_battle_body_submitted' and e.get('model')==model and e.get('result')==1 and e.get('drawable')==1 for e in events)
review=json.loads((META/'visual_review.json').read_text())
assert review['approved'] and review['run']==RUN and review['artifact_sha256']==proof['sha256']
def sha(b):return hashlib.sha256(b).hexdigest()
def source_at(path):
 return subprocess.check_output(['git','show',TESTED+':'+path])
mapping=json.loads((ROOT/'toeo-recovery/v18/source_map.json').read_text())
rows=[{'local':r['local'],'git_path':r['git_path']} for r in mapping['files']]
for name in ('world_enemy_packets.py','world_combat_packets.py','combat_runtime.js','combat_ci_acceptance.py','emulate_enemy.py','emulate_combat.py','world_battle_commands.py','test_battle_commands.py'):
 rows.append({'local':name,'git_path':'toeo-tests/'+name})
assert len({r['local'] for r in rows})==len(rows)==126
work=Path(os.environ['RUNNER_TEMP'])/'TOEO_V21_RELEASE';source=work/'toeo-tests';source.mkdir(parents=True,exist_ok=True)
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
unit_count=int(re.search(r'Ran (\d+) tests?',test.stdout).group(1));assert unit_count>=61
for name in ('Run_TOEO_Local.cmd','Run_TOEO_Rashuan.cmd','Prepare_TOEO_Client.cmd','Run_TOEO_Encounter_Test.cmd'):
 files[name]=source_at(name)
cmd=files['Run_TOEO_Rashuan.cmd'].decode().replace('--world-profile rashuan','--world-profile rashuan --equipment-preview')
files['Run_TOEO_Equipment_Test.cmd']=cmd.replace('\r\n','\n').replace('\n','\r\n').encode()
files['requirements_native.txt']=b'frida\npillow\n'
files['README_CN.txt']=(META/'README_CN.txt').read_bytes()
files['NEXT_RECOVERY_V21.txt']=(META/'NEXT_RECOVERY_V21.txt').read_bytes()
files['TOEO_RESTORATION_CURRENT_STATE.txt']=(META/'TOEO_RESTORATION_CURRENT_STATE.txt').read_bytes()
for name in ('artifact.json','runtime_result.json','event_counts.json','native_events.json','server.jsonl'):
 files['evidence/v21/'+name]=(EVIDENCE/name).read_bytes()
images=[]
for name,digest in review['images_sha256'].items():
 body=(EVIDENCE/name).read_bytes();assert sha(body)==digest
 images.append({'file':name,'sha256':digest,'alterations':'Exact original desktop crop only'})
files['evidence/v21/next_battle_protocol_notes.json']=(META/'next_battle_protocol_notes.json').read_bytes()
files['evidence/v21/original_enemy_resource_basis.json']=(ROOT/'toeo-recovery/v20/original_enemy_resource_basis.json').read_bytes()
protocol=ROOT/'toeo-recovery/v19/verification'/TESTED
assert json.loads((protocol/'native_battle_record.json').read_text())['passed']
for name in ('native_battle_record.json','native_enemy.json','unit_checks.txt'):
 files['evidence/v21/protocol/'+name]=(protocol/name).read_bytes()
files['evidence/v21/action_verification.json']=(META/'action_verification.json').read_bytes()
files['evidence/v21/visual_review.json']=(META/'visual_review.json').read_bytes()
files['evidence/v21/unit_tests.txt']=test.stdout.encode()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'User-Agent':'TOEO-baseline-verification','Accept':'application/vnd.github+json'}
def api(path):
 return json.loads(urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/adaierk/glb/'+path,headers=headers),timeout=60).read())
baseline_run=config['baseline_run']
a=next(x for x in api('actions/runs/'+str(baseline_run)+'/artifacts')['artifacts'] if x['name']=='toeo-original-gui-baseline')
assert a['workflow_run']['head_sha']==TESTED
try:raw=urllib.request.build_opener(NoRedirect()).open(urllib.request.Request(a['archive_download_url'],headers=headers),timeout=90).read()
except urllib.error.HTTPError as e:
 if e.code not in (301,302,303,307,308):raise
 raw=urllib.request.urlopen(e.headers['Location'],timeout=120).read()
assert 'sha256:'+sha(raw)==a['digest']
bz=zipfile.ZipFile(io.BytesIO(raw));assert bz.testzip() is None
first=json.loads(bz.read('first/runtime_result.json'));reentered=json.loads(bz.read('reentered/runtime_result.json'))
for r in (first,reentered):
 assert all(r.get(k) for k in ('map_entered','equipment_matches_database_native','equipment_hp_bonus_native','hp_gauge_draw_succeeded_native','visual_components_match_database_native','body_visual_resource_loaded_native','weapon_visual_resource_loaded_native','appearance_restored'))
assert first['native_equip_unequip_reequip_transitions'] and first['native_visual_equip_unequip_reequip_transitions'] and first['body_unequip_fallback_native']
assert reentered['position_restored_without_movement'] and first['saved_inventory']==reentered['saved_inventory']
baseline={'run':baseline_run,'tested_commit':TESTED,'artifact':a['id'],'sha256':sha(raw),'passed':True,'first':first,'reentered':reentered}
(META/'baseline_regression.json').write_text(json.dumps(baseline,indent=2))
files['evidence/v21/baseline_regression.json']=(META/'baseline_regression.json').read_bytes()
consistency={'passed':True,'tested_commit':TESTED,'count':len(rows),'files':rows}
(META/'source_consistency.json').write_text(json.dumps(consistency,indent=2))
files['evidence/v21/source_consistency.json']=json.dumps(consistency,indent=2).encode()
metadata={'version':'v21','tested_commit':TESTED,'windows_run_id':RUN,'windows_artifact':proof['artifact'],
 'windows_artifact_sha256':proof['sha256'],'source_files_verified':len(rows),'local_checks_passed':unit_count,
 'native_battle_target_attack_requests_verified':True,'native_battle_movement_action_records_verified':True,'native_basic_attack_animation_verified':True,'native_map_enemy_verified':True,'native_battle_actors_visually_verified':True,'screenshots_delivered_separately':True,'native_encounter_entry':config.get('encounter_entry',False),
 'complete_combat':False,'complete_gameplay':False,'original_exe_changed':False,'original_exe_sha256':'635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55',
 'original_assets_included':False,'user_database_included':False,'enemy_provenance':'Explicit local SLIME test; official spawn/stat configuration unresolved',
 'limitations':config['limitations'],'images':images,
 'files_sha256':{n:sha(b) for n,b in sorted(files.items())}}
files['RELEASE_METADATA.json']=json.dumps(metadata,ensure_ascii=False,indent=2).encode()
dest=META/'TOEO_Local_World_Recovery_20261010_v21.zip';prefix='TOEO_Local_World_v21/'
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for n,b in sorted(files.items()):z.writestr(prefix+n,b)
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None and all(z.read(prefix+n)==b for n,b in files.items())
 assert not any('.sqlite' in n or '__pycache__' in n or 'userdata/' in n for n in z.namelist())
manifest={'version':'v21','sha256':sha(dest.read_bytes()),'bytes':dest.stat().st_size,'entries':len(files),
 'crc_check':'PASS','source_consistency':'PASS','tested_commit':TESTED,'windows_run_id':RUN,
 'windows_artifact_sha256':proof['sha256'],'source_files_verified':len(rows),'local_checks_passed':unit_count,
 'complete_combat':False,'images':images,'limitations':config['limitations']}
(META/'MANIFEST_V21_SEALED.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('V21_NATIVE_RELEASE_SEALED',json.dumps(manifest,ensure_ascii=False))

screenshot_files={name:(EVIDENCE/name).read_bytes() for name in review['images_sha256']}
screenshot_files['SCREENSHOTS_CN.txt']=('永恒传说 OL v21 原客户端实机截图\n来源：Windows run '+str(RUN)+'，源提交 '+TESTED+'\n仅裁切游戏窗口；没有重绘、生成或修改游戏内容。\n原生选敌和普通攻击请求已接通；完整伤害、AI、结算及返回地图仍未完成。\n').encode('utf-8')
screenshot_files['SCREENSHOT_METADATA.json']=json.dumps({'version':'v21','tested_commit':TESTED,'windows_run_id':RUN,'artifact_sha256':proof['sha256'],'files_sha256':{name:sha(body) for name,body in screenshot_files.items()}},ensure_ascii=False,indent=2).encode()
screenshot_dest=META/'TOEO_Screenshots_20261010_v21.zip'
with zipfile.ZipFile(screenshot_dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name,body in sorted(screenshot_files.items()):z.writestr('TOEO_Screenshots_v21/'+name,body)
with zipfile.ZipFile(screenshot_dest) as z:
 assert z.testzip() is None and all(z.read('TOEO_Screenshots_v21/'+name)==body for name,body in screenshot_files.items())
manifest['screenshots_archive']={'file':screenshot_dest.name,'sha256':sha(screenshot_dest.read_bytes()),'bytes':screenshot_dest.stat().st_size,'entries':len(screenshot_files),'crc_check':'PASS'}
assert not any(name.endswith('.png') for name in files)
(META/'MANIFEST_V21_SEALED.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('V21_SEPARATE_SCREENSHOT_ARCHIVE_SEALED',json.dumps(manifest['screenshots_archive']))
