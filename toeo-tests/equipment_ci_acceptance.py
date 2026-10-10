"""Strict equipment Windows proof; no game-memory setters or UI fabrication."""
def verify_equipment(result,events,server,args,expected_position):
    roles=server.characters.list(1);identity=roles[0]['identity']
    saved=server.inventory.load(1,identity);vitals=server.inventory.load_vitals(1,identity)
    samples=[e for e in events if e.get('event')=='native_player_equipment_state']
    result['saved_inventory']=saved;result['saved_vitals']=vitals
    result['native_equipment_samples']=samples
    expected=[{'slot':x['slot'],'identity':list(x['identity'])} for x in saved['equipment']]
    actual=[{'slot':x['slot'],'identity':x['identity']} for x in samples[-1]['order']] if samples else []
    result['equipment_matches_database_native']=actual==expected and len(expected)==2
    result['equipment_fixture_provenance']='Explicit offline Local Test Sword/Body, not official item masters or historical shop stock'
    requests=[e for e in events if e.get('event')=='native_item_move_builder_enter']
    result['equip_request_native']=any(e['source_location']==2 and e['destination_location']==4 for e in requests)
    result['unequip_request_native']=any(e['source_location']==4 and e['destination_location']==2 for e in requests)
    result['native_vitals_samples']=[e for e in events if e.get('event')=='native_player_vitals_state']
    result['equipment_hp_bonus_native']=any(e.get('max_hp')==110 for e in result['native_vitals_samples']) and vitals['max_hp']==110
    result['hp_gauge_draw_succeeded_native']=any(e.get('event')=='native_hud_graphics_result' and e.get('hresult')=='0x0' and '0x5a0605' in e.get('stack',[]) for e in events)
    result['appearance_restored']=False
    if not result['map_entered'] or not result['equipment_matches_database_native'] or not result['equipment_hp_bonus_native'] or not result['hp_gauge_draw_succeeded_native']:return 'Native equipment map/state/HP/render acceptance failed'
    if not args.reenter_check and not (result['equip_request_native'] and result['unequip_request_native']):return 'Real mouse equip and unequip did not both occur'
    if args.reenter_check:
        result['position_restored_without_movement']=all(tuple(x)==expected_position for x in result['observed_positions'])
        if not result['position_restored_without_movement']:return 'Equipment restart position mismatch'
    return None
