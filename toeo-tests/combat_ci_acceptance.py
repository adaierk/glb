"""Acceptance for original enemy actor, model and actual native picking."""
from world_enemy_packets import ENEMY_IDENTITY,ENEMY_MODEL_BANK
def verify_combat(result,events,server,args,expected_position):
    created=[e for e in events if e.get('event')=='native_local_enemy_created']
    models=[e for e in events if e.get('event')=='native_local_enemy_state']
    target=[e for e in events if e.get('event')=='native_actor_target_set' and e.get('target')==list(ENEMY_IDENTITY)]
    picks=[e for e in events if e.get('event')=='native_player_pick_result' and any(a.get('identity')==list(ENEMY_IDENTITY) for a in e.get('actors',[]))]
    result.update(enemy_created_native=bool(created),
        enemy_component_native=any(e.get('extension',{}).get('kind')==1 for e in created if e.get('extension')),
        enemy_world_model_native=any(e.get('world_model') not in (None,'0x0') for e in created+models),
        enemy_target_selected_native=bool(target),enemy_mouse_pick_native=bool(picks),
        encounter_fixture_provenance='Original CID0 SLIME ID1200 -> CTY2RS SLIME -> CRSD se000 field bank800, explicit local entity, HP100 and spawn',
        combat_flow_complete=False)
    return None if all(result.get(k) for k in ('map_entered','enemy_created_native','enemy_component_native','enemy_world_model_native','enemy_mouse_pick_native','enemy_target_selected_native')) else 'Original enemy creation/model/picking/target protocol checks did not all pass'
