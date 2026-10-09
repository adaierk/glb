"""Package a verified original-client NPC/shop milestone; never generate a screen."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from PIL import Image


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--run',type=int,required=True)
    a.add_argument('--tested-commit',required=True)
    a.add_argument('--checkpoint-commit',required=True)
    a.add_argument('--workflow-run',type=int,required=True)
    a.add_argument('--artifact',type=int,required=True)
    x=a.parse_args()
    w=Path(__file__).resolve().parent
    out=w.parent/'deliverables';out.mkdir(exist_ok=True)
    evidence=w/'new_evidence'/f'windows_run{x.run}'
    first=json.loads((evidence/'first/runtime_result.json').read_text())
    second=json.loads((evidence/'reentered/runtime_result.json').read_text())
    for key in ['map_entered','npc_selected_native','shop_catalog_parsed_native','shop_frame_shown_native','shop_closed_native','movement_after_shop_close_native']:
        assert first[key] is True,key
    assert second['map_entered'] and second['position_restored_without_movement']
    assert second['expected_reentry_position']==[640.,128.]
    final_proof=json.loads((w/'new_evidence/auth/v12_actual_world_milestone.json').read_text())
    assert final_proof['passed'] and final_proof['tested_commit']==x.tested_commit
    root='TOEO_Local_World_v12/'
    files={}
    baseline=out/'TOEO_Local_World_Recovery_20261009_v11.zip'
    assert sha(baseline.read_bytes())=='4293f0b064e9f255f2f28db179435cbc4b850169dcd845c599a30a4b3bfdf93c'
    with zipfile.ZipFile(baseline) as z:
        for name in z.namelist():
            relative=name.split('/',1)[1]
            if relative.startswith(('evidence/native/','history/')):
                files[relative]=z.read(name)
            elif relative=='NEXT_RECOVERY_V11.txt':
                files['history/NEXT_RECOVERY_V11_UNMODIFIED.txt']=z.read(name)
    for name in ['Run_TOEO_Local.cmd','Prepare_TOEO_Client.cmd','requirements_native.txt',
                 'TOEO_RESTORATION_CURRENT_STATE.txt','NEXT_RECOVERY_V12.txt']:
        files[name]=(w/name).read_bytes()
    files['README_CN.txt']=(w/'README_V12_CN.txt').read_bytes()
    for p in (w/'toeo-tests').iterdir():
        if p.suffix in ('.py','.js'):
            files['toeo-tests/'+p.name]=p.read_bytes()
    for p in (w/'history').glob('*.txt'):
        files['history/'+p.name]=p.read_bytes()
    for p in (w/'new_evidence/auth').glob('v12_*.json'):
        files['evidence/native/'+p.name]=p.read_bytes()
    for p in (w/'new_evidence/reverse_v12').glob('*.txt'):
        files['evidence/reverse/'+p.name]=p.read_bytes()
    selections={
        'first':{140,142,146,149,150,160,170,180},
        'reentered':{140,150}}
    for phase,seconds in selections.items():
        for p in (evidence/phase).iterdir():
            if p.suffix in ('.json','.jsonl','.txt') or p.name.startswith('client_11101_') and p.suffix=='.bin':
                files[f'evidence/windows_run{x.run}/{phase}/{p.name}']=p.read_bytes()
        for second_value in seconds:
            p=evidence/phase/f'original_desktop_{second_value:03d}s.png'
            if p.exists():files[f'evidence/windows_run{x.run}/{phase}/{p.name}']=p.read_bytes()
    image_provenance=[]
    for source,name in [
        ('first/original_desktop_146s.png','TOEO_Local_Shop_20261009_v12.png'),
        ('reentered/original_desktop_150s.png','TOEO_Local_World_20261009_v12.png')]:
        source_path=evidence/source
        original=Image.open(source_path)
        crop=original.crop((8,32,808,632));display=out/name;crop.save(display)
        assert Image.open(display).tobytes()==crop.tobytes()
        files['evidence/'+name]=display.read_bytes()
        image_provenance.append({'source':source,'source_sha256':sha(source_path.read_bytes()),
                                 'display_file':name,'display_sha256':sha(display.read_bytes()),
                                 'crop':[8,32,808,632],'alterations':'Desktop crop only; all game pixels unchanged'})
    metadata={'version':'v12','tested_code_commit':x.tested_commit,'checkpoint_commit':x.checkpoint_commit,
              'windows_run_id':x.workflow_run,'artifact_id':x.artifact,'local_checks_passed':32,
              'native_npc_pick_verified':True,'native_target_and_shop_verified':True,
              'shop_hidden_by_actual_title_bar_click':True,'movement_after_shop_close_verified':True,
              'restart_position_verified':[19,7],'empty_shop_catalog':True,'buy_sell_verified':False,
              'complete_gameplay':False,'original_assets_included':False,'user_database_included':False,
              'images':image_provenance,'files_sha256':{k:sha(v) for k,v in sorted(files.items())}}
    files['RELEASE_METADATA.json']=json.dumps(metadata,ensure_ascii=False,indent=2).encode()
    destination=out/'TOEO_Local_World_Recovery_20261009_v12.zip'
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):z.writestr(root+name,data)
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(files)
        for name,data in files.items():assert z.read(root+name)==data,name
        assert not any('.sqlite' in n or 'local_world_userdata/' in n for n in z.namelist())
        for p in (w/'toeo-tests').iterdir():
            if p.suffix in ('.py','.js'):assert z.read(root+'toeo-tests/'+p.name)==p.read_bytes()
    manifest={'zip':str(destination),'sha256':sha(destination.read_bytes()),'bytes':destination.stat().st_size,
              'entries':len(files),'crc_check':'PASS','archive_sources_match_current_files':'PASS',
              'user_database_included':False,'checkpoint_commit':x.checkpoint_commit}
    (w/'MANIFEST_V12.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
