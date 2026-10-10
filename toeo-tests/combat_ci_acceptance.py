"""Acceptance for original enemy actor, model and actual native picking."""
from world_enemy_packets import ENEMY_IDENTITY,ENEMY_MODEL_BANK
def verify_combat(result,events,server,args,expected_position):
    created=[e for e in events if e.get('event')=='native_local_enemy_created']
    models=[e for e in events if e.get('event')=='native_local_enemy_state']
    symbols=[e for e in events if e.get('event')=='native_enemy_symbol_created' and e.get('resource')==1500000 and e.get('result') not in (None,'0x0')]
    target=[e for e in events if e.get('event')=='native_actor_target_set' and e.get('target')==list(ENEMY_IDENTITY)]
    picks=[e for e in events if e.get('event')=='native_player_pick_result' and any(a.get('identity')==list(ENEMY_IDENTITY) for a in e.get('actors',[]))]
    import json
    wire=[json.loads(line) for line in (server.out/'server.jsonl').read_text().splitlines() if line.strip()]
    acknowledged=[e for e in wire if e.get('event')=='encounter_ack_native']
    ready=[e for e in wire if e.get('event')=='battle_resource_reply_sent']
    player_models=[e for e in events if e.get('event')=='native_battle_actor_model_load' and e.get('identity')==[1,1] and e.get('result')==1 and e.get('model') not in (None,'0x0')]
    enemy_models=[e for e in events if e.get('event')=='native_battle_actor_model_load' and e.get('identity')==list(ENEMY_IDENTITY) and e.get('result')==1 and e.get('model') not in (None,'0x0')]
    pending=[e.get('request_id') for e in events if e.get('event')=='native_battle_pending_request_completed']
    result.update(enemy_created_native=bool(created),
        enemy_component_native=any(e.get('extension',{}).get('kind')==1 for e in created if e.get('extension')),
        enemy_world_model_native=any(e.get('world_model') not in (None,'0x0') for e in created+models),
        enemy_field_symbol_native=bool(symbols),enemy_target_selected_native=bool(target),enemy_mouse_pick_native=bool(picks),
        encounter_fixture_provenance='Original CID0 SLIME ID1200 -> CTY2RS SLIME -> CRSD se000 field bank800, explicit local entity, HP100 and spawn',
        encounter_native_confirmed=bool(acknowledged),battle_player_model_native=bool(player_models),battle_enemy_model_native=bool(enemy_models),
        battle_scene_initialized_native=any(e.get('event')=='native_battle_init_returned' for e in events),
        battle_resource_ack_native=bool(ready) and any(e.get('request_id') in pending for e in ready),
        combat_flow_complete=False)
    return None if all(result.get(k) for k in ('map_entered','enemy_created_native','enemy_component_native','enemy_field_symbol_native','enemy_mouse_pick_native','enemy_target_selected_native','encounter_native_confirmed','battle_player_model_native','battle_enemy_model_native','battle_scene_initialized_native','battle_resource_ack_native')) else 'Original enemy creation/symbol/picking/target protocol checks did not all pass'
