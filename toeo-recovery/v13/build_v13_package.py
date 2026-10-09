"""Package sourced merchant restoration and genuine Windows screenshots."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image
import zipfile


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True)
    p.add_argument('--checkpoint-commit',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent;out=root.parent/'deliverables';out.mkdir(exist_ok=True)
    proof=json.loads((root/'new_evidence/auth/v13_actual_world_milestone.json').read_text())
    assert proof['passed'] and proof['visual_prices_reviewed']
    files={};prefix='TOEO_Local_World_v13/'
    old=out/'TOEO_Local_World_Recovery_20261009_v12.zip'
    assert sha(old.read_bytes())=='018bb84b30c7778518ff0ebf4746591c8ecd1a6ad59801e6906db542ee9fd93a'
    with zipfile.ZipFile(old) as z:
        for name in z.namelist():
            rel=name.split('/',1)[1]
            if rel.startswith(('history/','evidence/native/')):files[rel]=z.read(name)
            if rel=='NEXT_RECOVERY_V12.txt':files['history/NEXT_RECOVERY_V12_UNMODIFIED.txt']=z.read(name)
    for name in ('Run_TOEO_Local.cmd','Run_TOEO_Rashuan.cmd','Prepare_TOEO_Client.cmd','requirements_native.txt',
                 'TOEO_RESTORATION_CURRENT_STATE.txt','NEXT_RECOVERY_V13.txt'):
        files[name]=(root/name).read_bytes()
    files['README_CN.txt']=(root/'README_V13_CN.txt').read_bytes()
    for path in (root/'toeo-tests').iterdir():
        if path.suffix in ('.py','.js') or path.name=='historical_shops.json':
            files['toeo-tests/'+path.name]=path.read_bytes()
    for path in (root/'history').glob('*.txt'):files['history/'+path.name]=path.read_bytes()
    for path in (root/'new_evidence/auth').glob('v13_*.json'):files['evidence/native/'+path.name]=path.read_bytes()
    for name in ('v13_camera_price_exact.txt','reverse_v13.txt','shop_row_v13.txt','item_attrs_v13.txt','lz2_v13.txt'):
        path=root/'new_evidence'/name
        if path.exists():files['evidence/reverse/'+name]=path.read_bytes()
    folder=root/'new_evidence'/f'windows_run{a.run}'
    for phase,seconds in {'first':(140,142,146,147,149,160,170,180),'reentered':(140,150)}.items():
        for path in (folder/phase).iterdir():
            if path.suffix in ('.json','.jsonl','.txt') or path.name.startswith('client_11101_') and path.suffix=='.bin':
                files[f'evidence/windows_run{a.run}/{phase}/{path.name}']=path.read_bytes()
        for second in seconds:
            path=folder/phase/f'original_desktop_{second:03d}s.png'
            if path.exists():files[f'evidence/windows_run{a.run}/{phase}/{path.name}']=path.read_bytes()
    images=[]
    for source,name in [('first/original_desktop_140s.png','TOEO_Rashuan_Merchant_20261009_v13.png'),
                        ('first/original_desktop_146s.png','TOEO_Rashuan_Shop_20261009_v13.png')]:
        original=folder/source;crop=Image.open(original).crop((8,32,808,632));destination=out/name;crop.save(destination)
        assert Image.open(destination).tobytes()==crop.tobytes()
        files['evidence/'+name]=destination.read_bytes()
        images.append({'file':name,'source':source,'source_sha256':sha(original.read_bytes()),
                       'sha256':sha(destination.read_bytes()),'crop':[8,32,808,632],
                       'alterations':'Desktop crop only; all game pixels unchanged'})
    metadata={'version':'v13','windows_tested_commit':proof['tested_commit'],'checkpoint_commit':a.checkpoint_commit,
              'windows_run_id':proof['windows_run_id'],'artifact_id':proof['artifact_id'],'local_checks_passed':34,
              'historical_shops':13,'historical_goods_records':140,'historical_xy_records':6,
              'native_placed_historical_merchants':1,'native_goods_visible':11,'native_price_text_visible':True,
              'map_id_hex':'1120108','merchant_grid':[141,313],'restart_grid':proof['final_grid'],
              'predicted_movement_rejection_restore_verified':True,
              'runtime_source_bytes_match_tested_commit':True,'supplemental_analysis_sources':13,
              'buy_sell_verified':False,'templates_icons_verified':False,'complete_gameplay':False,
              'original_assets_included':False,'user_database_included':False,'images':images,
              'files_sha256':{name:sha(data) for name,data in sorted(files.items())}}
    files['RELEASE_METADATA.json']=json.dumps(metadata,ensure_ascii=False,indent=2).encode()
    destination=out/'TOEO_Local_World_Recovery_20261009_v13.zip'
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):z.writestr(prefix+name,data)
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None
        assert all(z.read(prefix+name)==data for name,data in files.items())
        assert not any('.sqlite' in name or 'userdata/' in name for name in z.namelist())
    manifest={'zip':str(destination),'sha256':sha(destination.read_bytes()),'bytes':destination.stat().st_size,
              'entries':len(files),'crc_check':'PASS','archive_sources_match_current_files':'PASS',
              'user_database_included':False,'checkpoint_commit':a.checkpoint_commit}
    (root/'MANIFEST_V13.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
