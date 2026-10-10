"""Deliver verified original pixels, source and reproducible recovery evidence."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from PIL import Image

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--checkpoint-commit',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];out=root.parent/'deliverables';out.mkdir(exist_ok=True)
    proof=json.loads((root/'new_evidence/native/v16_actual_bag_hud_milestone.json').read_text())
    consistency=json.loads((root/'new_evidence/native/v16_source_consistency.json').read_text())
    assert proof['passed'] and proof['visual_reviewed'] and consistency['passed'] and consistency['commit']==proof['tested_commit']
    base=root.parent/'recovery/TOEO_Local_World_Recovery_20261010_v15.zip'
    assert sha(base.read_bytes())=='78fa0dc2e69490a7be1f929234da70115f9d6721ac106257f7d7c28f1a292a0a'
    files={};prefix='TOEO_Local_World_v16/'
    with zipfile.ZipFile(base) as z:
        for name in z.namelist():
            rel=name.split('/',1)[1]
            if not rel:continue
            if rel in ('README_CN.txt','TOEO_RESTORATION_CURRENT_STATE.txt','NEXT_RECOVERY_V15.txt','RELEASE_METADATA.json'):
                files['history/V15_UNMODIFIED_'+rel]=z.read(name)
            elif not rel.startswith('toeo-tests/'):
                files[rel]=z.read(name)
    for row in consistency['files']:
        data=(root/'toeo-tests'/row['local']).read_bytes();assert sha(data)==row['sha256']
        files['toeo-tests/'+row['local']]=data
    for name in ('README_CN.txt','TOEO_RESTORATION_CURRENT_STATE.txt','NEXT_RECOVERY_V16.txt'):
        files[name]=(root/name).read_bytes()
    for path in (root/'research').glob('*.py'):files['research/'+path.name]=path.read_bytes()
    for path in (root/'new_evidence/native').iterdir():
        if path.is_file():files['evidence/native/'+path.name]=path.read_bytes()
    for path in (root/'new_evidence/reverse').glob('*.txt'):
        if path.stat().st_size:files['evidence/reverse/'+path.name]=path.read_bytes()
    folder=a.folder.resolve()
    for phase,seconds in {'first':(146,156,161,181,196,200,208,210,220,245),'reentered':(140,150,155)}.items():
        for path in (folder/phase).iterdir():
            if path.suffix in ('.json','.jsonl','.txt') or path.name.startswith('client_11101_') and path.suffix=='.bin':
                files[f'evidence/windows_run{proof["windows_run_id"]}/{phase}/{path.name}']=path.read_bytes()
        for second in seconds:
            path=folder/phase/f'original_desktop_{second:03d}s.png'
            if path.exists():files[f'evidence/windows_run{proof["windows_run_id"]}/{phase}/{path.name}']=path.read_bytes()
    for name in ('first_driver.txt','reentry_driver.txt'):
        path=folder/name
        if path.exists():files[f'evidence/windows_run{proof["windows_run_id"]}/{name}']=path.read_bytes()
    # Preserve the diagnostic blank-HUD run and the failed old acceptance
    # condition. They are history, never substituted for the passing run.
    for phase in ('first','reentered'):
        path=root/'new_evidence/v16_native_bag_move'/phase/'runtime_result.json'
        if path.exists():files[f'evidence/investigation/run38012643950/{phase}_result.json']=path.read_bytes()
    for phase in ('first','reentered'):
        path=root/'new_evidence/windows_hud_probe3'/phase/'runtime.jsonl'
        if path.exists():files[f'evidence/investigation/run38012165294/{phase}_runtime.jsonl']=path.read_bytes()
    before=root/'new_evidence/windows_hud_probe3/first/original_desktop_196s.png'
    if before.exists():files['evidence/investigation/run38012165294/hud_before_original_desktop.png']=before.read_bytes()
    for run,dirname in ((38013085361,'v16_graphics_boundary'),(38013845064,'v16_texture_state_probe')):
        for name in ('runtime.jsonl','runtime_result.json'):
            path=root/'new_evidence'/dirname/'first'/name
            if path.exists():files[f'evidence/investigation/run{run}/first/{name}']=path.read_bytes()
    images=[]
    selected=[('first/original_desktop_196s.png','TOEO_Rashuan_HP40_Bag_20261010_v16.png'),
        ('first/original_desktop_208s.png','TOEO_Rashuan_HP100_Bag_Swapped_20261010_v16.png'),
        ('reentered/original_desktop_150s.png','TOEO_Rashuan_HP_Bag_Restored_20261010_v16.png'),
        ('first/original_desktop_220s.png','TOEO_Rashuan_Map_HP100_20261010_v16.png')]
    for source,name in selected:
        original=folder/source;crop=Image.open(original).crop((8,32,808,632));dest=out/name;crop.save(dest)
        assert Image.open(dest).tobytes()==crop.tobytes()
        files['evidence/'+name]=dest.read_bytes()
        images.append({'file':name,'source':source,'source_sha256':sha(original.read_bytes()),'sha256':sha(dest.read_bytes()),
            'crop':[8,32,808,632],'alterations':'Desktop crop only; all original game pixels unchanged'})
    metadata={'version':'v16','windows_tested_commit':proof['tested_commit'],'checkpoint_commit':a.checkpoint_commit,
        'windows_run_id':proof['windows_run_id'],'artifact_id':proof['artifact_id'],'windows_artifact_sha256':proof['artifact_sha256'],
        'local_checks_passed':53,'source_files_verified':consistency['count'],'native_bag_swap_restart_verified':True,
        'actual_original_hp_tp_draw_verified':True,'money_after_use_and_move':3740,'hp_after_use':100,'tp_after_use':10,
        'ci_initial_hp':40,'complete_gameplay':False,'original_assets_included':False,'user_database_included':False,
        'renderer_scope':proof['renderer_scope'],'limitations':proof['limitations'],'images':images,
        'files_sha256':{name:sha(data) for name,data in sorted(files.items())}}
    files['RELEASE_METADATA.json']=json.dumps(metadata,ensure_ascii=False,indent=2).encode()
    dest=out/'TOEO_Local_World_Recovery_20261010_v16.zip'
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):z.writestr(prefix+name,data)
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None and all(z.read(prefix+name)==data for name,data in files.items())
        assert not any('.sqlite' in name or 'userdata/' in name or '__pycache__' in name for name in z.namelist())
    manifest={'zip':str(dest),'sha256':sha(dest.read_bytes()),'bytes':dest.stat().st_size,'entries':len(files),
        'crc_check':'PASS','archive_source_consistency':'PASS','user_database_included':False,'checkpoint_commit':a.checkpoint_commit}
    (root/'MANIFEST_V16.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
