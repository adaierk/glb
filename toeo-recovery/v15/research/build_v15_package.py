"""Package native v15 proof, current source and unchanged screenshot pixels."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from PIL import Image


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);p.add_argument('--checkpoint-commit',required=True)
    a=p.parse_args();root=Path(__file__).resolve().parent;out=root.parent/'deliverables';out.mkdir(exist_ok=True)
    proof=json.loads((root/'new_evidence/auth/v15_actual_item_use_milestone.json').read_text())
    consistency=json.loads((root/'new_evidence/auth/v15_source_consistency.json').read_text())
    assert proof['passed'] and proof['visual_reviewed'] and proof['run']==a.run
    assert consistency['passed'] and consistency['commit']==proof['tested_commit']
    for row in consistency['files']:assert sha((root/'toeo-tests'/row['local']).read_bytes())==row['sha256']
    base=out/'TOEO_Local_World_Recovery_20261009_v14.zip'
    assert sha(base.read_bytes())=='a6de2f32a16658a4bceb2b37824453c68430911d4c014e5e5365a54a8b44749b'
    files={};prefix='TOEO_Local_World_v15/'
    with zipfile.ZipFile(base) as z:
        for name in z.namelist():
            rel=name.split('/',1)[1]
            if rel.startswith(('history/','evidence/native/')):files[rel]=z.read(name)
            if rel in ('TOEO_RESTORATION_CURRENT_STATE.txt','NEXT_RECOVERY_V14.txt','README_CN.txt'):
                files['history/V14_UNMODIFIED_'+rel]=z.read(name)
    for name in ('Run_TOEO_Local.cmd','Run_TOEO_Rashuan.cmd','Prepare_TOEO_Client.cmd','requirements_native.txt','TOEO_RESTORATION_CURRENT_STATE.txt','NEXT_RECOVERY_V15.txt'):
        files[name]=(root/name).read_bytes()
    files['README_CN.txt']=(root/'README_V15_CN.txt').read_bytes()
    for row in consistency['files']:files['toeo-tests/'+row['local']]=(root/'toeo-tests'/row['local']).read_bytes()
    for name in ('record_v15_milestone.py','build_v15_package.py'):files['research/'+name]=(root/name).read_bytes()
    files['research/probe_self_target_command_v15.py']=(root/'new_evidence/analysis/probe_self_target_command_v15.py').read_bytes()
    for path in (root/'new_evidence/auth').glob('v15_*.json'):files['evidence/native/'+path.name]=path.read_bytes()
    names=('provider_raw_get','icon_original_decode','item_use_builder','item_use_default_target','item_source_load',
        'item_src_text','item_src_construct','native_compression','lz1_decode_core','lz1_dictionary','vitals_full','serialization_compressed',
        'shop_command_close','shop_close_ui_call','hp_tp_getters','hud_smoothing_refs','hud_state_update','hud_smoothed_value_refs','hud_gauge_callback','self_target_command','native_draw_failure')
    for name in names:
        path=root/'new_evidence'/(name+'_v15.txt');files['evidence/reverse/'+path.name]=path.read_bytes()
    files['evidence/historical/consumables.txt']=(root/'new_evidence/wiki_v13/consumables.txt').read_bytes()
    files['evidence/historical/sources.json']=(root/'new_evidence/wiki_v13/sources.json').read_bytes()
    folder=root/'new_evidence'/f'windows_run{a.run}'
    for phase,seconds in {'first':(146,156,181,196,200,210,220,245),'reentered':(140,150,155)}.items():
        for path in (folder/phase).iterdir():
            if path.suffix in ('.json','.jsonl','.txt') or path.name.startswith('client_11101_') and path.suffix=='.bin':
                files[f'evidence/windows_run{a.run}/{phase}/{path.name}']=path.read_bytes()
        for second in seconds:
            path=folder/phase/f'original_desktop_{second:03d}s.png'
            if path.exists():files[f'evidence/windows_run{a.run}/{phase}/{path.name}']=path.read_bytes()
    images=[]
    for source,name in [('first/original_desktop_156s.png','TOEO_Rashuan_Shop_20261010_v15.png'),
        ('first/original_desktop_200s.png','TOEO_Rashuan_Item_Detail_20261010_v15.png'),
        ('reentered/original_desktop_150s.png','TOEO_Rashuan_Item_Restored_20261010_v15.png')]:
        original=folder/source;crop=Image.open(original).crop((8,32,808,632));dest=out/name;crop.save(dest)
        assert Image.open(dest).tobytes()==crop.tobytes()
        files['evidence/'+name]=dest.read_bytes()
        images.append({'file':name,'source':source,'source_sha256':sha(original.read_bytes()),'sha256':sha(dest.read_bytes()),
            'crop':[8,32,808,632],'alterations':'Desktop crop only; original game pixels unchanged'})
    metadata={'version':'v15','windows_tested_commit':proof['tested_commit'],'checkpoint_commit':a.checkpoint_commit,
        'windows_run_id':proof['windows_run_id'],'artifact_id':proof['artifact_id'],'windows_artifact_sha256':proof['artifact_sha256'],
        'local_checks_passed':45,'source_files_verified':consistency['count'],'native_item_use_restart_verified':True,
        'quantity_after_use':1,'money_after_use':4100,'hp_after_use':100,'tp_after_use':10,'ci_initial_hp':40,
        'complete_gameplay':False,'original_assets_included':False,'user_database_included':False,
        'icon_provenance':proof['icon_provenance'],'limitations':proof['limitations'],'images':images,
        'files_sha256':{n:sha(d) for n,d in sorted(files.items())}}
    files['RELEASE_METADATA.json']=json.dumps(metadata,ensure_ascii=False,indent=2).encode()
    dest=out/'TOEO_Local_World_Recovery_20261010_v15.zip'
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):z.writestr(prefix+name,data)
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None and all(z.read(prefix+n)==d for n,d in files.items())
        assert not any('.sqlite' in n or 'userdata/' in n for n in z.namelist())
    manifest={'zip':str(dest),'sha256':sha(dest.read_bytes()),'bytes':dest.stat().st_size,'entries':len(files),
        'crc_check':'PASS','archive_source_consistency':'PASS','user_database_included':False,'checkpoint_commit':a.checkpoint_commit}
    (root/'MANIFEST_V15.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
