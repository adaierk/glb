"""Record verified original Windows observations, without altering evidence."""
import argparse, hashlib, json, sqlite3
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=int, required=True)
    p.add_argument('--tested-commit', required=True)
    p.add_argument('--workflow-run', type=int, required=True)
    p.add_argument('--artifact', type=int, required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parent
    evidence = root / 'new_evidence' / f'windows_run{a.run}'
    results = {}
    logs = {}
    for phase in ('first', 'reentered'):
        folder = evidence / phase
        results[phase] = json.loads((folder / 'runtime_result.json').read_text())
        logs[phase] = {
            n: [json.loads(line) for line in (folder / f'{n}.jsonl').read_text().splitlines()]
            for n in ('runtime', 'server')
        }
    first, second = results['first'], results['reentered']
    for key in ('map_entered', 'npc_selected_native', 'shop_catalog_parsed_native',
                'shop_frame_shown_native', 'shop_closed_native', 'movement_after_shop_close_native'):
        assert first[key] is True, key
    assert second['map_entered'] and second['position_restored_without_movement']
    assert second['expected_reentry_position'] == [640., 128.]
    moves = [e for e in logs['first']['server'] if e.get('event') == 'world_move_ack']
    second_moves = [e for e in logs['reentered']['server'] if e.get('event') == 'world_move_ack']
    assert moves and moves[-1]['target'] == [19, 7]
    assert not second_moves
    restored = [e for e in logs['reentered']['server'] if e.get('restored') is True]
    assert restored, 'No server restored-position evidence'
    assert all(e.get('grid') == [19, 7] for e in restored)
    with sqlite3.connect(evidence / 'first' / 'local_accounts.sqlite') as db:
        rows = db.execute('SELECT * FROM world_positions').fetchall()
        columns = [x[1] for x in db.execute('PRAGMA table_info(world_positions)')]
    assert any(dict(zip(columns, row)).get('grid_x') == 19 and
               dict(zip(columns, row)).get('grid_y') == 7 for row in rows)
    source_images = {}
    for name in ('first/original_desktop_146s.png', 'first/original_desktop_149s.png',
                 'first/original_desktop_170s.png', 'reentered/original_desktop_150s.png'):
        source_images[name] = hashlib.sha256((evidence / name).read_bytes()).hexdigest()
    events = logs['first']['runtime']
    state = [e for e in events if e.get('event') == 'native_shop_frame_state']
    visible = [e for e in state if e.get('visible') is True]
    assert visible
    hidden = [e for e in state if e.get('visible') is False and e['host_time'] > visible[0]['host_time']]
    assert hidden
    assert state[-1]['visible'] is False
    assert all(e['visible'] is False for e in state if e['host_time'] >= hidden[0]['host_time'])
    proof = {
        'passed': True, 'tested_commit': a.tested_commit,
        'windows_run_id': a.workflow_run, 'artifact_id': a.artifact,
        'map_entered': first['map_entered'], 'npc_selected_native': first['npc_selected_native'],
        'native_empty_shop_parsed': first['shop_catalog_parsed_native'],
        'native_shop_frame_shown': first['shop_frame_shown_native'],
        'native_shop_frame_hidden_after_show': first['shop_closed_native'],
        'movement_after_shop_close_native': first['movement_after_shop_close_native'],
        'shop_parse_events': [e for e in events if e.get('event') == 'native_shop_catalog_parse_result'],
        'shop_visibility_transitions': [e for e in events if e.get('event') == 'native_shop_visibility_change'],
        'first_visible_shop_state': visible[0], 'first_hidden_shop_state_after_show': hidden[0],
        'native_requests': [e for e in logs['first']['server'] if e.get('event') in
                            ('actor_target_answer', 'native_npc_request', 'shop_catalog_ack_native')],
        'first_movement_acks': moves, 'final_original_renderer_position': first['observed_positions'][-1],
        'database_world_positions_columns': columns, 'database_world_positions_rows': rows,
        'reentry_restored_without_movement': second['position_restored_without_movement'],
        'reentry_samples': len(second['observed_positions']),
        'reentry_unique_positions': sorted(set(tuple(x) for x in second['observed_positions'])),
        'reentry_movement_acks': len(second_moves), 'server_restored_events': restored,
        'source_image_sha256': source_images,
        'original_ui_input': {'merchant_left_clicks': [[424,145],[424,145]],
                              'title_bar_close_click': [493,107],
                              'road_clicks': [[360,180],[620,160]]},
        'visual_observations': [
            'Original desktop146: native Japanese shop with purchase/sell controls; empty catalog.',
            'Original desktop149: actual title-bar X hides shop; merchant target HUD remains.',
            'Original desktop170: character walked to grid(19,7), shop remains hidden.',
            'Reentered desktop150: original map and minimap X0019 Y0007 restored.'
        ],
        'validation_scope': 'Actual Windows desktop, original function observations and TCP captures; no success-state injection.',
        'limitations': [
            'Empty catalog and money 0; buying/selling, inventory and complete gameplay remain unfinished.',
            'NPC identity/name/location are local reconstruction, not recovered official merchant data.',
            'UI/resource C++ exceptions remain; logs retained.',
            'Visibility flag reads independently corroborate actual screenshots; fixtures are separately scoped.'
        ]
    }
    destination = root / 'new_evidence/auth/v12_actual_world_milestone.json'
    destination.write_text(json.dumps(proof, ensure_ascii=False, indent=2))
    print(json.dumps({'passed': True, 'run': a.run, 'move_acks': len(moves),
                      'reentry_samples': proof['reentry_samples'], 'reentry_move_acks': 0}))


if __name__ == '__main__':
    main()
