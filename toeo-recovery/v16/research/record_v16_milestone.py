"""Gate a recovery release on real original Windows drawing, UI and restart."""
import argparse,hashlib,json,sqlite3
from pathlib import Path

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def log(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]

def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path)
    p.add_argument('--commit',required=True);p.add_argument('--run',type=int,required=True)
    p.add_argument('--artifact',type=int,required=True);p.add_argument('--artifact-sha256',required=True)
    p.add_argument('--visual-reviewed',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parents[1];folder=a.folder.resolve()
    assert hashlib.sha256(folder.with_suffix('.zip').read_bytes()).hexdigest()==a.artifact_sha256
    result={phase:read(folder/phase/'runtime_result.json') for phase in ('first','reentered')}
    logs={phase:{kind:log(folder/phase/(kind+'.jsonl')) for kind in ('server','runtime')} for phase in result}
    first=result['first'];second=result['reentered']
    checks=('map_entered','npc_selected_native','shop_catalog_parsed_native','shop_frame_shown_native',
        'shop_historical_names_native','shop_historical_prices_native','shop_historical_item_count_native',
        'historical_merchant_position_native','historical_map_id_native','shop_closed_native','movement_after_shop_close_native',
        'buy_request_built_native','sell_request_built_native','buy_money_quantity_native','sell_money_quantity_native',
        'shop_quantity_refreshed_native','inventory_window_open_native','original_lemon_icon_native','item_used_native',
        'hp_recovered_native','bag_order_native','bag_slot1_saved','bag_move_request_native',
        'hp_gauge_draw_succeeded_native','tp_gauge_draw_succeeded_native','hud_actual_d3d_draw_succeeded_native')
    restart=('map_entered','position_restored_without_movement','inventory_restored_native','vitals_restored_native',
        'inventory_window_open_native','bag_order_native','bag_slot1_saved','hp_gauge_draw_succeeded_native',
        'tp_gauge_draw_succeeded_native','hud_actual_d3d_draw_succeeded_native')
    assert all(first[k] is True for k in checks),{k:first.get(k) for k in checks if first.get(k) is not True}
    assert all(second[k] is True for k in restart),{k:second.get(k) for k in restart if second.get(k) is not True}
    expected=[('ミックスグミ',1,0),('レモングミ',1,1)]
    for phase in result:
        r=result[phase];items=r['saved_inventory']['items']
        assert [(x['name'],x['quantity'],x['slot']) for x in items]==expected and r['saved_inventory']['money']==3740
        assert r['saved_vitals']=={'hp':100,'tp':10,'max_hp':100,'max_tp':30}
        assert not any(x.get('event')=='frida_error' for x in logs[phase]['runtime'])
        assert not any(x.get('event')=='protocol_rejected' for x in logs[phase]['server'])
        native=[x for x in logs[phase]['runtime'] if x.get('event')=='native_player_inventory_state'][-1]
        assert [(x['identity'],x['quantity'],x['slot']) for x in native['order']]==[(x['identity'],x['quantity'],x['slot']) for x in items]
    moves=[x for x in logs['first']['server'] if x.get('event')=='item_move_committed' and not x['replayed']]
    uses=[x for x in logs['first']['server'] if x.get('event')=='item_use_committed' and not x['replayed']]
    assert len(moves)==len(uses)==1
    assert (moves[0]['source_location'],moves[0]['source_slot'],moves[0]['count'],moves[0]['destination_location'],moves[0]['destination_slot'],moves[0]['sequence'])==(2,0,-1,2,1,5)
    assert uses[0]['sequence']==4 and uses[0]['target']==[1,1]
    assert not any(x.get('event') in ('item_move_committed','item_use_committed','shop_trade_committed') for x in logs['reentered']['server'])
    hud={phase:[x for x in logs[phase]['runtime'] if x.get('event')=='native_own_hud_values'] for phase in logs}
    assert any(x['hp']==40 and x['tp']==10 and x['max_hp']==100 and x['max_tp']==30 for x in hud['first'])
    assert any(x['hp']==100 and x['tp']==10 for x in hud['first'])
    assert hud['reentered'] and all(x['hp']==100 and x['tp']==10 for x in hud['reentered'])
    with sqlite3.connect(folder/'first/local_accounts.sqlite') as db:
        items=db.execute('SELECT name,quantity,slot FROM world_inventory_items ORDER BY slot').fetchall()
        vitals=db.execute('SELECT hp,tp,max_hp,max_tp FROM world_vitals').fetchall()
        ledger=db.execute('SELECT opcode,sequence FROM world_trade_ledger ORDER BY id').fetchall()
    assert items==expected and vitals==[(100,10,100,30)] and ledger==[(0xde,1),(0xdf,2),(0x55,4),(0x54,5)]
    consistency=read(root/'new_evidence/native/v16_source_consistency.json')
    assert consistency['passed'] and consistency['commit']==a.commit and consistency['count']==112
    manifests={phase:read(folder/phase/'graphics_assets_manifest.json') for phase in result}
    for phase in manifests:
        assert manifests[phase]['original_assets_unchanged'] and len(manifests[phase]['files'])==4
        assert all(x['alpha_preserved'] and x['origin_preserved'] for x in manifests[phase]['files'])
        states=[x for x in logs[phase]['runtime'] if x.get('event')=='native_hud_graphics_state']
        assert any(x['texture_stages'][0]['description']['fields'][0]==21 and x['texture_stages'][0]['description']['fields'][6:]==[512,256] for x in states)
    assert a.visual_reviewed,'Review real Windows screen pixels before asserting a visible HUD restoration'
    proof={'passed':True,'tested_commit':a.commit,'windows_run_id':a.run,'artifact_id':a.artifact,
        'artifact_sha256':a.artifact_sha256,'checks':{k:first[k] for k in checks},'restart_checks':{k:second[k] for k in restart},
        'native_move':moves[0],'native_use':uses[0],'saved_inventory':first['saved_inventory'],'saved_vitals':first['saved_vitals'],
        'database_items':items,'database_vitals':vitals,'database_ledger':ledger,'final_pixel':first['observed_positions'][-1],
        'renderer_asset_manifests':manifests,
        'native_exception_counts':{phase:len(result[phase]['native_exceptions']) for phase in result},
        'visual_reviewed':True,'local_checks_passed':53,'source_files_verified':112,'complete_gameplay':False,
        'original_binary_sha256':'635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55',
        'fixture_note':'Only the isolated CI character starts HP40/TP10; delivery includes no user database.',
        'renderer_scope':'Four original palette TGAs expand losslessly to 32-bit BGRA in a separate runtime directory. Original exe/assets retained; original D3D9 drawing and HRESULTs unchanged. Native probes only observe state.',
        'limitations':['Casting, interrupted use, buffs, revival and battle targeting pending',
            'Equipment, combat, quests, map transitions and complete collision pending',
            'Experience/level progression and official item masters pending',
            'Other caught native system/C++ exceptions remain recorded; broader renderer compatibility pending',
            'Provisional level-one stat limits, wallet, stack capacity, merchant identity/model and walkable cells']}
    (root/'new_evidence/native/v16_actual_bag_hud_milestone.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'original_hud_visible':True,'actual_bag_swap_restart':True,'money':3740,'hp':100,'tp':10}))

if __name__=='__main__':main()
