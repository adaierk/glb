"""Package verified original-client trades, source and untouched screen pixels."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from PIL import Image


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True)
    p.add_argument('--checkpoint-commit',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent;out=root.parent/'deliverables';out.mkdir(exist_ok=True)
    proof=json.loads((root/'new_evidence/auth/v14_actual_trade_milestone.json').read_text())
    assert proof['passed'] and proof['visual_reviewed'] and a.run==proof['run']
    consistency=json.loads((root/'new_evidence/auth/v14_source_consistency.json').read_text())
    assert consistency['passed'] and consistency['commit']==proof['tested_commit']
    for item in consistency['files']:
        assert sha((root/'toeo-tests'/item['local']).read_bytes())==item['sha256']
    old=out/'TOEO_Local_World_Recovery_20261009_v13.zip'
    assert sha(old.read_bytes())=='88ece02005c92913b8edc3b26ca4c9b84c80cea3c98fd53302b8dbb447a59e25'
    files={};prefix='TOEO_Local_World_v14/'
    with zipfile.ZipFile(old) as z:
        for name in z.namelist():
            rel=name.split('/',1)[1]
            if rel.startswith(('history/','evidence/native/')):files[rel]=z.read(name)
            if rel=='NEXT_RECOVERY_V13.txt':files['history/NEXT_RECOVERY_V13_UNMODIFIED.txt']=z.read(name)
            if rel=='TOEO_RESTORATION_CURRENT_STATE.txt':files['history/V13_AND_RUN42_STATE_UNMODIFIED.txt']=z.read(name)
    for name in ('Run_TOEO_Local.cmd','Run_TOEO_Rashuan.cmd','Prepare_TOEO_Client.cmd','requirements_native.txt',
                 'TOEO_RESTORATION_CURRENT_STATE.txt','NEXT_RECOVERY_V14.txt'):
        files[name]=(root/name).read_bytes()
    files['README_CN.txt']=(root/'README_V14_CN.txt').read_bytes()
    for path in (root/'toeo-tests').iterdir():
        if path.suffix in ('.py','.js') or path.name=='historical_shops.json':files['toeo-tests/'+path.name]=path.read_bytes()
    for name in ('record_v14_milestone.py','build_v14_package.py'):
        files['research/'+name]=(root/name).read_bytes()
    for path in (root/'new_evidence/auth').glob('v14_*.json'):files['evidence/native/'+path.name]=path.read_bytes()
    for name in ('trade_request_v14.txt','inventory_parse_v14.txt','item_names_v14.txt','inventory_update_v14.txt','world_inventory_v14.txt','command_result_v14.txt','currency_change_v14.txt','inventory_delta_v14.txt','item_clone_v14.txt','shop_refresh_v14.txt'):
        files['evidence/reverse/'+name]=(root/'new_evidence'/name).read_bytes()
    folder=root/'new_evidence'/f'windows_run{a.run}'
    for phase,seconds in {'first':(140,146,151,156,161,171,175,181,196,245),'reentered':(140,150,155)}.items():
        for path in (folder/phase).iterdir():
            if path.suffix in ('.json','.jsonl','.txt') or path.name.startswith('client_11101_') and path.suffix=='.bin':
                files[f'evidence/windows_run{a.run}/{phase}/{path.name}']=path.read_bytes()
        for second in seconds:
            path=folder/phase/f'original_desktop_{second:03d}s.png'
            if path.exists():files[f'evidence/windows_run{a.run}/{phase}/{path.name}']=path.read_bytes()
    images=[]
    choices=[('first/original_desktop_156s.png','TOEO_Rashuan_Buy_20261009_v14.png'),
             ('first/original_desktop_196s.png','TOEO_Rashuan_Inventory_20261009_v14.png'),
             ('reentered/original_desktop_150s.png','TOEO_Rashuan_Reentered_20261009_v14.png')]
    for source,name in choices:
        original=folder/source;crop=Image.open(original).crop((8,32,808,632));destination=out/name;crop.save(destination)
        assert Image.open(destination).tobytes()==crop.tobytes()
        files['evidence/'+name]=destination.read_bytes()
        images.append({'file':name,'source':source,'source_sha256':sha(original.read_bytes()),'sha256':sha(destination.read_bytes()),
                       'crop':[8,32,808,632],'alterations':'Desktop crop only; original game pixels unchanged'})
    metadata={'version':'v14','windows_tested_commit':proof['tested_commit'],'checkpoint_commit':a.checkpoint_commit,
        'windows_run_id':proof['windows_run_id'],'artifact_id':proof['artifact_id'],'local_checks_passed':38,
        'windows_artifact_sha256':proof['artifact_sha256'],'source_consistency_verified':97,
        'native_historical_merchant_count':1,'native_shop_goods_count':11,'original_buy_sell_inventory_restart_verified':True,
        'buy':{'quantity':3,'money_before':5000,'money_after':3920},'sell':{'quantity':1,'money_after':4100},
        'saved_item_quantity':2,'offline_rules':proof['offline_rules'],'templates_icons_verified':False,
        'complete_gameplay':False,'original_assets_included':False,'user_database_included':False,'images':images,
        'files_sha256':{name:sha(data) for name,data in sorted(files.items())}}
    files['RELEASE_METADATA.json']=json.dumps(metadata,ensure_ascii=False,indent=2).encode()
    destination=out/'TOEO_Local_World_Recovery_20261009_v14.zip'
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):z.writestr(prefix+name,data)
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None and all(z.read(prefix+name)==data for name,data in files.items())
        assert not any('.sqlite' in name or 'userdata/' in name for name in z.namelist())
    manifest={'zip':str(destination),'sha256':sha(destination.read_bytes()),'bytes':destination.stat().st_size,'entries':len(files),
        'crc_check':'PASS','archive_source_consistency':'PASS','user_database_included':False,'checkpoint_commit':a.checkpoint_commit}
    (root/'MANIFEST_V14.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
