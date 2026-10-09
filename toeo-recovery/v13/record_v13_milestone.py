"""Validate native river-map/merchant/stock/price/close/reentry evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys


def main():
    p=argparse.ArgumentParser(); p.add_argument('--run',type=int,required=True)
    p.add_argument('--tested-commit',required=True); p.add_argument('--workflow-run',type=int,required=True)
    p.add_argument('--artifact',type=int,required=True); p.add_argument('--visual-reviewed',action='store_true')
    a=p.parse_args(); root=Path(__file__).resolve().parent
    sys.path.insert(0,str(root/'toeo-tests'))
    from world_profiles import RASHUAN
    from native_map_geometry import grid_to_point
    from world_shop_catalog import historical_stock
    evidence=root/'new_evidence'/f'windows_run{a.run}'
    results={}; logs={}
    for phase in ('first','reentered'):
        folder=evidence/phase
        results[phase]=json.loads((folder/'runtime_result.json').read_text())
        logs[phase]={n:[json.loads(line) for line in (folder/f'{n}.jsonl').read_text().splitlines()]
                     for n in ('runtime','server')}
    first,second=results['first'],results['reentered']
    checks=('map_entered','npc_selected_native','shop_catalog_parsed_native','shop_frame_shown_native',
            'shop_historical_names_native','shop_historical_prices_native','shop_historical_item_count_native',
            'shop_display_price_text_native','historical_merchant_position_native','historical_map_id_native',
            'shop_closed_native','movement_after_shop_close_native')
    for key in checks: assert first[key] is True,key
    assert second['map_entered'] and second['position_restored_without_movement']
    stock=historical_stock(RASHUAN.stock_key)
    rows=[e for e in logs['first']['runtime'] if e.get('event')=='native_shop_row_render']
    assert [e['name'] for e in rows[:11]]==[x['name'] for x in stock['stock']]
    assert [e['catalog_display_value'] for e in rows[:11]]==[x['price_gald'] for x in stock['stock']]
    moves=[e for e in logs['first']['server'] if e.get('event')=='world_move_ack']
    assert moves and tuple(moves[-1]['target'])!=RASHUAN.spawn_grid
    rejected=[e for e in logs['first']['server'] if e.get('event')=='world_move_rejected_and_restored']
    assert rejected and all(e['status']==-93 for e in rejected)
    assert not any(e.get('event')=='world_move_ack' for e in logs['reentered']['server'])
    final_grid=tuple(moves[-1]['target']); final_pixel=grid_to_point(final_grid)
    assert tuple(first['observed_positions'][-1])==final_pixel
    assert tuple(second['expected_reentry_position'])==final_pixel
    restored=[e for e in logs['reentered']['server'] if e.get('restored') is True]
    assert restored and all(tuple(e['grid'])==final_grid and e['map_id']==RASHUAN.map_id for e in restored)
    with sqlite3.connect(evidence/'first/local_accounts.sqlite') as db:
        saved=db.execute('SELECT character_id,account_id,map_id,grid_x,grid_y FROM world_profile_positions').fetchall()
    assert any(row[2]==RASHUAN.map_id and tuple(row[3:])==final_grid for row in saved)
    assert not any(e.get('event')=='frida_error' for phase in logs.values() for e in phase['runtime'])
    images={name:hashlib.sha256((evidence/name).read_bytes()).hexdigest() for name in (
        'first/original_desktop_140s.png','first/original_desktop_146s.png',
        'first/original_desktop_147s.png','first/original_desktop_170s.png','reentered/original_desktop_150s.png')}
    assert a.visual_reviewed,'Actual desktop pixels must be reviewed before release'
    proof={'passed':True,'tested_commit':a.tested_commit,'windows_run_id':a.workflow_run,'artifact_id':a.artifact,
           'checks':{key:first[key] for key in checks},'visual_prices_reviewed':True,
           'map_id_hex':'1120108','map_name':RASHUAN.label,'merchant_name':RASHUAN.merchant_name,
           'merchant_grid':list(RASHUAN.merchant_grid),'merchant_pixel':list(grid_to_point(RASHUAN.merchant_grid)),
           'map_identity_basis':'Original minimap pixels visually match named historical Wiki map; this is an inference',
           'source_url':stock['source_url'],'goods':stock['stock'],'native_rows':rows,
           'display_price_text_events':[e for e in logs['first']['runtime'] if e.get('event')=='native_shop_display_price_text'],
           'first_movement_acks':moves,'native_rejection_restore_events':rejected,'final_grid':list(final_grid),'final_pixel':list(final_pixel),
           'database_rows':saved,'reentry_restored_without_movement':True,
           'reentry_samples':len(second['observed_positions']),'source_image_sha256':images,
           'validation_scope':'Original Windows desktop, read-only original parser/renderer observations and TCP captures',
           'limitations':['Historical merchant position/name/stock sourced from community Wiki; original server database unavailable',
                          'Native entity ID and humanoid appearance are local choices; original templates/icons still unknown',
                          '178 conservative pier navigation cells; wider map collision and transitions pending',
                          'Currency 0; buying/selling, inventory, quests and combat not implemented',
                          'Original UI/resource C++ first-chance exception logs retained; HP/TP digits unfinished']}
    (root/'new_evidence/auth/v13_actual_world_milestone.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'goods':len(stock['stock']),'final_grid':final_grid,
                      'reentry_samples':proof['reentry_samples']},ensure_ascii=False))


if __name__=='__main__':main()
