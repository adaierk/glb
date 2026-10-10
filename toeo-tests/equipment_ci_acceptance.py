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
    
    visual_samples=[e for e in events if e.get('event')=='native_player_visual_state']
    result['native_visual_samples']=visual_samples
    expected_components=[{'slot':x['slot'],'identity':list(x['identity']),'resource':10000 if x['slot']==1 else 4000,'layer':4 if x['slot']==1 else 1,'source_bank':500 if x['slot']==1 else 0} for x in saved['equipment']]
    result['visual_components_match_database_native']=bool(visual_samples) and visual_samples[-1]['components']==expected_components
    def loaded(e,layer,resource):
        return any(x['layer']==layer and x['resource']==resource and x.get('native_component') not in (None,'0x0') for x in e.get('layers',[]))
    result['body_visual_resource_loaded_native']=bool(visual_samples) and loaded(visual_samples[-1],1,4000)
    result['weapon_visual_resource_loaded_native']=bool(visual_samples) and loaded(visual_samples[-1],4,10000)
    weapon_layers=[x for x in visual_samples[-1].get('layers',[]) if x['layer']==4 and x['resource']==10000] if visual_samples else []
    descriptor=weapon_layers[-1].get('descriptor') if weapon_layers else None
    result['native_weapon_descriptor']=descriptor
    result['weapon_map_hidden_by_original_asset']=bool(descriptor) and descriptor['symbol']=='ID_SWORD_000' and descriptor['map_amd']=='' and descriptor['map_bnd']=='' and descriptor['battle_amd']=='b_sword.amd' and descriptor['battle_bnd']=='b_sword_000.bnd'
    if not result['weapon_map_hidden_by_original_asset']:return 'Original sword descriptor map/battle sprite fields were not observed'
    result['appearance_restored']=all(result[k] for k in ('visual_components_match_database_native','body_visual_resource_loaded_native','weapon_visual_resource_loaded_native'))
    if not result['appearance_restored']:return 'Original world model clothing resources or component identities did not match saved equipment'
    if not args.reenter_check:
        appearance_states=[tuple(x['slot'] for x in e['components']) for e in visual_samples];at=-1
        try:
            for state in ((1,),(1,2),(2,),(1,2),(1,),(1,2)):at=appearance_states.index(state,at+1)
        except ValueError:return 'Original visual component equip/unequip sequence missing'
        result['native_visual_equip_unequip_reequip_transitions']=True
        result['body_unequip_fallback_native']=any(tuple(x['slot'] for x in e['components'])==(1,) and loaded(e,1,200) for e in visual_samples)
        if not result['body_unequip_fallback_native']:return 'Body unequip did not reload original base-body resource'

    if not result['map_entered'] or not result['equipment_matches_database_native'] or not result['equipment_hp_bonus_native'] or not result['hp_gauge_draw_succeeded_native']:return 'Native equipment map/state/HP/render acceptance failed'
    if not args.reenter_check:
        states=[tuple(x['slot'] for x in e['order']) for e in samples];position=-1
        try:
            for expected in ((1,),(1,2),(2,),(1,2),(1,),(1,2)):position=states.index(expected,position+1)
        except ValueError:return 'Actual native equip, unequip and re-equip state sequence missing'
        result['native_equip_unequip_reequip_transitions']=True
        if not (result['equip_request_native'] and result['unequip_request_native']):return 'Real mouse equip and unequip did not both occur'
    if args.reenter_check:
        result['position_restored_without_movement']=all(tuple(x)==expected_position for x in result['observed_positions'])
        if not result['position_restored_without_movement']:return 'Equipment restart position mismatch'
    return None
