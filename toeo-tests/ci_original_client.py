"""Exercise the original Windows GUI against the recovered loopback server.

UI input uses actual mouse/keyboard controls. Captures are the Windows desktop;
native observations and screenshots are preserved without inferred map success.
"""
import argparse,ctypes,faulthandler,hashlib,json,os,shutil,time,traceback
from pathlib import Path
from local_account_server import LocalAccountServer
from character_mutation_packets import create_character_request

SHA='635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'

def main():
    p=argparse.ArgumentParser();p.add_argument('game');p.add_argument('out')
    p.add_argument('--duration',type=int,default=180);p.add_argument('--pump',action='store_true')
    p.add_argument('--database',help='Reuse a preserved local account database for the reentry check')
    p.add_argument('--reenter-check',action='store_true',help='Observe the restored position without scheduled movement')
    p.add_argument('--use-check',action='store_true',help='Seed this isolated test character at HP40/TP10, then require a real native use and restart')
    p.add_argument('--equipment-check',action='store_true',help='Real native equip/unequip and restart using explicitly local equipment fixtures')
    p.add_argument('--move-check',action='store_true',help='Require real two-item bag exchange and original client restart restoration')
    p.add_argument('--resource-probe',action='store_true',help='Read-only resource discovery; not a gameplay acceptance run')
    p.add_argument('--combat-check',action='store_true',help='Original enemy encounter fixture through real mouse input')
    args=p.parse_args()
    if os.name!='nt':raise SystemExit('Windows original-client verification required')
    import frida
    from PIL import ImageGrab
    game=Path(args.game).resolve();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    diagnostic=(out/'python_threads.txt').open('w',encoding='utf-8');faulthandler.enable(diagnostic);faulthandler.dump_traceback_later(45,repeat=True,file=diagnostic)
    original=game/'ToEO_CL.dat'
    if hashlib.sha256(original.read_bytes()).hexdigest()!=SHA:raise SystemExit('Original SHA mismatch')
    from legacy_graphics_assets import prepare_render_client
    game=prepare_render_client(game,game.parent/'game_runtime_v16',out/'graphics_assets_manifest.json')
    original=game/'ToEO_CL.dat'
    exe=game/'ToEO_CL_local_ci.exe';shutil.copyfile(original,exe)
    server=LocalAccountServer(out,world_route_probe=True,account_database=args.database,shop_preview=True,world_profile='rashuan',combat_preview=args.combat_check)
    if not server.characters.list(1):server.characters.create(1,create_character_request('Archive'))
    if args.equipment_check and not args.reenter_check:server.inventory.grant_equipment_preview(1,server.characters.list(1)[0]['identity'])
    events=[];shots=[];device=frida.get_local_device();pid=None;session=None;failure=None
    from native_map_geometry import grid_to_point
    expected_position=grid_to_point(server.positions.load(1,server.characters.list(1)[0]['identity'])['grid'])
    expected_inventory=server.inventory.load(1,server.characters.list(1)[0]['identity'])
    if args.use_check and not args.reenter_check:
        # CharacterStore.list takes the same non-reentrant database lock.
        # Resolve the identity before opening this isolated test transaction.
        test_identity=server.characters.list(1)[0]['identity']
        with server.accounts.lock,server.accounts.db:
            server.accounts.db.execute('UPDATE world_vitals SET hp=40,tp=10 WHERE character_id=? AND account_id=?',test_identity)
    expected_vitals=server.inventory.load_vitals(1,server.characters.list(1)[0]['identity'])
    u=ctypes.windll.user32
    def click(x,y,right=False,hold=.90):
        u.SetCursorPos(x,y);time.sleep(.15);u.mouse_event(8 if right else 2,0,0,0,0);time.sleep(hold);u.mouse_event(16 if right else 4,0,0,0,0);time.sleep(.35)
        events.append({'event':'actual_ui_click','x':x,'y':y,'right':right,'host_time':time.time()});print('PHASE actual_ui_click '+str((x,y)),flush=True)
    def type_text(s):
        for c in s:
            code=u.VkKeyScanW(ord(c))
            if code==-1:raise ValueError('Character is not available on the native keyboard')
            vk=code&255;modifiers=[key for bit,key in ((1,16),(2,17),(4,18)) if (code>>8)&bit]
            for key in modifiers:u.keybd_event(key,0,0,0)
            u.keybd_event(vk,0,0,0);u.keybd_event(vk,0,2,0)
            for key in reversed(modifiers):u.keybd_event(key,0,2,0)
            time.sleep(.04)
    def self_target_command():
        # Original 4C68C0 with no argument constructs 4E target=self.
        # Enter opens native chat input; no game function is called or patched.
        u.keybd_event(13,0,0,0);time.sleep(.08);u.keybd_event(13,0,2,0);time.sleep(.3)
        type_text('/target')
        u.keybd_event(13,0,0,0);time.sleep(.08);u.keybd_event(13,0,2,0);time.sleep(.5)
        events.append({'event':'actual_ui_chat_command','command':'/target','host_time':time.time()})
    def double_click(x,y):
        u.SetCursorPos(x,y);time.sleep(.15)
        for _ in range(2):
            u.mouse_event(2,0,0,0,0);time.sleep(.08);u.mouse_event(4,0,0,0,0);time.sleep(.08)
        time.sleep(.35);events.append({'event':'actual_ui_double_click','x':x,'y':y,'host_time':time.time()})
    def drag(x,y,tx,ty):
        u.SetCursorPos(x,y);time.sleep(.2);u.mouse_event(2,0,0,0,0);time.sleep(.4)
        for step in range(1,11):
            u.SetCursorPos(round(x+(tx-x)*step/10),round(y+(ty-y)*step/10));time.sleep(.08)
        time.sleep(.3);u.mouse_event(4,0,0,0,0);time.sleep(.4)
        events.append({'event':'actual_ui_drag','from':[x,y],'to':[tx,ty],'host_time':time.time()})
    def has_cart():return any(e.get('event')=='native_shop_cart_add_result' and e.get('result')==1 for e in events)
    def adjust_quantity(mode,target):
        samples=[e for e in events if e.get('event')=='native_shop_cart_state' and e.get('mode')==mode and e.get('lines')==1]
        if not samples:return
        quantity=samples[-1]['quantity']
        if quantity<target:click(441,186,hold=.15)
        elif quantity>target:click(441,202,hold=.15)
    with (out/'runtime.jsonl').open('w',encoding='utf-8',buffering=1) as log:
        def receive(m,data):
            row=m.get('payload',m) if m.get('type')=='send' else {'event':'frida_error','detail':m}
            row['host_time']=time.time();events.append(row);log.write(json.dumps(row,ensure_ascii=False,default=str)+'\n')
            if row.get('event','').endswith('_NATIVE') or row.get('event') in ('native_exception','frida_error'):
                print(json.dumps(row,ensure_ascii=False),flush=True)
        def shot(t):
            path=out/f'original_desktop_{t:03d}s.png';ImageGrab.grab().save(path)
            shots.append({'file':path.name,'elapsed':t,'scope':'actual Windows desktop'})
        try:
            print('PHASE server_start',flush=True);server.start()
            print('PHASE original_spawn',flush=True);pid=device.spawn([str(exe)],cwd=str(game))
            print('PHASE original_attach pid='+str(pid),flush=True);session=device.attach(pid)
            session.on('detached',lambda reason,crash: receive({'type':'send','payload':{'event':'detached','reason':reason,'crash':str(crash)}},None))
            source='\n'.join(Path(__file__).with_name(n).read_text(encoding='utf-8') for n in
                             ('bootstrap_runtime.js','account_runtime.js','offline_socket_compat.js','offline_graphics_compat.js'))
            if args.combat_check:source+='\n'+Path(__file__).with_name('combat_runtime.js').read_text(encoding='utf-8')
            if args.pump:source+='\n'+Path(__file__).with_name('native_gui_pump.js').read_text(encoding='utf-8')
            if args.resource_probe:source+='\n'+Path(__file__).with_name('resource_probe.js').read_text(encoding='utf-8')
            print('PHASE native_hooks_load',flush=True)
            script=session.create_script(source);script.on('message',receive);script.load()
            print('PHASE hooks_loaded',flush=True)
            deadline=time.monotonic()+5
            while not any(e.get('event')=='offline_socket_compat_ready' for e in events) and time.monotonic()<deadline:time.sleep(.05)
            if not any(e.get('event')=='offline_socket_compat_ready' for e in events):raise RuntimeError('Hook readiness failed')
            print('PHASE original_resume',flush=True);device.resume(pid)
            print('PHASE original_gui_running',flush=True)
            schedule={34:lambda:click(408,447),45:lambda:click(218,534),
                      78:lambda:click(360,299),82:lambda:click(340,391),
                      92:lambda:(click(380,290),type_text('archive001')),
                      96:lambda:(click(380,336),type_text('local123')),100:lambda:click(315,405),
                      115:lambda:click(325,150),120:lambda:click(700,447),
                      125:lambda:(click(323,303),click(323,324),click(450,376)),
                      130:lambda:click(450,376),
                      135:lambda:click(700,447),
                      141:lambda:click(472,341),145:lambda:click(472,341),
                      147:lambda:[click(271,411,hold=.15) for _ in range(6)],
                      148:lambda:[click(271,183,hold=.15) for _ in range(6)],
                      150:lambda:double_click(107,195),
                      152:lambda:None if has_cart() else drag(107,195,324,195),
                      153:lambda:adjust_quantity(0,3),155:lambda:adjust_quantity(0,3),157:lambda:adjust_quantity(0,3),
                      160:lambda:click(349,409),170:lambda:click(159,142),
                      174:lambda:double_click(107,195),176:lambda:drag(107,195,324,195) if not any(e.get('event')=='native_shop_cart_add_result' and e.get('result')==1 and e.get('mode')==1 for e in events) else None,
                      177:lambda:adjust_quantity(1,1),178:lambda:adjust_quantity(1,1),
                      180:lambda:click(349,409),
                      190:lambda:click(493,107),195:lambda:click(28,84),
                      198:lambda:click(517,487,right=True),201:lambda:click(316,430),
                      202:lambda:click(28,84),203:self_target_command,204:lambda:click(28,84),
                      205:lambda:double_click(517,487),
                      210:lambda:click(28,84),215:lambda:click(360,410,hold=2.0),
                      225:lambda:click(480,380,hold=2.0),235:lambda:click(400,350,True)}
            if args.move_check:schedule.update({158:lambda:double_click(107,229),207:lambda:drag(517,487,555,487)})
            if args.reenter_check:
                # The client recreates its tutorial confirmation on each launch.
                # Retain that real UI flow; only omit movement in this run.
                for t in tuple(schedule):
                    if t>=141:schedule.pop(t,None)
                schedule.update({145:lambda:click(28,84)})
            if args.equipment_check:
                for t in tuple(schedule):
                    if t>=141:schedule.pop(t,None)
                if args.reenter_check:schedule.update({145:lambda:click(28,84)})
                else:schedule.update({145:lambda:click(28,84),150:lambda:drag(517,487,658,263),165:lambda:drag(517,487,706,263),180:lambda:drag(658,263,517,487),195:lambda:drag(517,487,658,263),210:lambda:drag(706,263,517,487),225:lambda:drag(517,487,706,263),245:lambda:click(28,84),250:lambda:click(360,410,hold=2)})
            if args.combat_check:
                for t in tuple(schedule):
                    if t>=141:schedule.pop(t,None)
                schedule.update({145:lambda:click(344,341),148:lambda:click(344,350),
                                 151:lambda:click(344,350,right=True),154:lambda:double_click(344,350)})
            for t in range(args.duration):
                time.sleep(1)
                entered=any(e.get('event')=='native_map_draw_context' for e in events)
                if t in schedule and not (t in (125,130,135) and entered):schedule[t]()
                if t%10==0 or t in (101,107,121,126,136,142,146,147,149,151,156,161,171,175,181,191,196,208):shot(t);print('PHASE screenshot '+str(t),flush=True)
        except Exception:
            failure=traceback.format_exc()
            (out/'python_error.txt').write_text(failure,encoding='utf-8');traceback.print_exc()
        finally:
            try:shot(args.duration)
            except Exception:pass
            (out/'screenshots.json').write_text(json.dumps(shots,indent=2),encoding='utf-8')
            names={e.get('event') for e in events}
            result={key:True if value in names else None for key,value in
                    [('native_session_created','OWN_SESSION_CREATED_NATIVE'),('account_authenticated','ACCOUNT_AUTHENTICATED_NATIVE'),
                     ('game_prelogin_accepted','GAME_PRELOGIN_ACCEPTED_NATIVE'),('character_list_accepted','CHARACTER_LIST_ACCEPTED_NATIVE'),
                     ('character_selection_accepted','CHARACTER_SELECTION_ACCEPTED_NATIVE'),('world_admission_accepted','WORLD_ADMISSION_ACK_ACCEPTED_NATIVE'),
                     ('world_controller_completed','WORLD_CONTROLLER_COMPLETED_NATIVE')]}
            positions=[e['position'] for e in events if e.get('event')=='native_world_render_state' and 'position' in e]
            result.update(map_entered=('native_map_enter_transition' in names and bool(positions)),playable=None,
                          observed_positions=positions,expected_reentry_position=list(expected_position) if args.reenter_check else None,
                          native_exceptions=[e for e in events if e.get('event')=='native_exception'])
            result['npc_selected_native']=any(e.get('event')=='native_npc_actions' and e.get('identity')==[0x70000001,1] for e in events)
            result['shop_catalog_parsed_native']=any(e.get('event')=='native_shop_catalog_parse_result' and e.get('result')==1 and e.get('target')==[0x70000001,1] for e in events)
            result['shop_frame_shown_native']=any(e.get('event')=='native_shop_frame_show' and e.get('result')==1 for e in events)
            from world_shop_catalog import historical_stock,PREVIEW_SOURCE_KEY
            expected_stock=historical_stock(PREVIEW_SOURCE_KEY)['stock']
            rendered_names=[e.get('name') for e in events if e.get('event')=='native_shop_row_render']
            built_prices=[e.get('price_gald') for e in events if e.get('event')=='native_shop_item_insert']
            result['shop_historical_names_native']=all(x['name'] in rendered_names for x in expected_stock)
            result['shop_historical_prices_native']=built_prices[:len(expected_stock)]==[x['price_gald'] for x in expected_stock]
            result['shop_historical_item_count_native']=any(e.get('event')=='native_shop_catalog_parse_result' and e.get('result')==1 and e.get('items')==len(expected_stock) for e in events)
            created=[e for e in events if e.get('event')=='native_local_shop_create_result']
            result['historical_merchant_position_native']=any(tuple(e.get('position') or ())==grid_to_point(server.profile.merchant_grid) for e in created)
            result['historical_map_id_native']=any(e.get('event')=='native_world_render_state' and e.get('current_map_id')==server.map_id for e in events)
            result['historical_placement_basis']='Original minimap visually matches Wiki named map; Wiki XY reproduced by native actor grid conversion'
            displayed=[e.get('text') for e in events if e.get('event')=='native_shop_display_price_text']
            result['shop_display_price_text_native']=all(str(x['price_gald']) in displayed for x in expected_stock)
            result['visible_prices_verified']=None  # Separately reviewed from captured desktop pixels.
            result['official_item_master_ids_verified']=False
            result['original_lemon_icon_native']=any(e.get('event')=='native_inventory_ui_item' and e.get('icon_id')==3811 for e in events)
            result['icon_name_association_basis']='Visual match against unchanged original ICND sprites'
            inventory_samples=[e for e in events if e.get('event')=='native_player_inventory_state']
            named_items=[e for e in events if e.get('event')=='native_inventory_named_item']
            result['native_inventory_samples']=inventory_samples
            saved_inventory=server.inventory.load(1,server.characters.list(1)[0]['identity'])
            result['saved_inventory']=saved_inventory
            if args.combat_check:
                from combat_ci_acceptance import verify_combat
                combat_failure=verify_combat(result,events,server,args,expected_position)
                if combat_failure:failure=failure or combat_failure
            elif args.equipment_check:
                from equipment_ci_acceptance import verify_equipment
                equipment_failure=verify_equipment(result,events,server,args,expected_position)
                (out/'runtime_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                if equipment_failure:failure=failure or equipment_failure
            else:
                if args.move_check:
                    expected_order=[(list(x['identity']),x['quantity'],x['slot']) for x in saved_inventory['items']]
                    # Original initial 34/6B reconstruction appends with argument -1.
                    # Verify the actual native linked list, not the insertion argument.
                    result['bag_order_native']=bool(inventory_samples) and [(x['identity'],x['quantity'],x['slot']) for x in inventory_samples[-1].get('order',[])]==expected_order
                    lemon=next((x for x in saved_inventory['items'] if x['name']=='レモングミ'),None)
                    result['bag_slot1_native']=result['bag_order_native'] and lemon is not None and lemon['slot']==1
                    result['bag_slot1_saved']=len(saved_inventory['items'])==2 and next((x['slot'] for x in saved_inventory['items'] if x['name']=='レモングミ'),None)==1
                    result['bag_move_request_native']=any(e.get('event')=='native_plain_request_before_serialization' and e.get('opcode')==0x54 for e in events)
                    if not result['bag_slot1_native'] or not result['bag_slot1_saved'] or (not args.reenter_check and not result['bag_move_request_native']):
                        failure=failure or 'Real native bag move and persistent bag order did not pass'

                result['saved_vitals']=server.inventory.load_vitals(1,server.characters.list(1)[0]['identity'])
                hud_draws=[e for e in events if e.get('event')=='native_hud_graphics_result' and e.get('hresult')=='0x0']
                result['hp_gauge_draw_succeeded_native']=any('0x5a0605' in e.get('stack',[]) for e in hud_draws)
                result['tp_gauge_draw_succeeded_native']=any('0x5a0675' in e.get('stack',[]) for e in hud_draws)
                result['hud_actual_d3d_draw_succeeded_native']=any(e.get('event')=='native_hud_d3d_method_result' and e.get('method')=='DrawPrimitiveUP' and e.get('hresult')=='0x0' for e in events)
                result['renderer_optional_validation_compat_applied']='legacy_render_validation_compat_applied' in names
                if not all(result[k] for k in ('hp_gauge_draw_succeeded_native','tp_gauge_draw_succeeded_native','hud_actual_d3d_draw_succeeded_native')):
                    failure=failure or 'Actual original HP/TP primitive drawing did not succeed'
                vital_samples=[e for e in events if e.get('event')=='native_player_vitals_state']
                result['native_vitals_samples']=vital_samples
                if args.use_check and not args.reenter_check:
                    owned_items={tuple(item['identity']) for item in saved_inventory['items']}
                    # Item-source descriptions also pass through 51D930 and have
                    # quantity1; require the actual owned bag instance in 565210.
                    result['item_used_native']=any(e.get('event')=='native_item_use_builder_result' and e.get('result')==1 for e in events) and any(e.get('event')=='native_inventory_ui_item' and e.get('quantity')==1 and e.get('icon_id')==3811 and tuple(e.get('identity',())) in owned_items for e in events)
                    result['hp_recovered_native']=any(e.get('hp')==40 and e.get('tp')==10 for e in vital_samples) and any(e.get('hp')==100 and e.get('tp')==10 for e in vital_samples)
                    if not result['item_used_native'] or not result['hp_recovered_native']:failure=failure or 'Real native item use / quantity 1 / HP40 to 100 did not pass'
                result['buy_request_built_native']=any(e.get('event')=='native_trade_builder_result' and e.get('kind')=='buy' and e.get('result')==1 for e in events)
                result['sell_request_built_native']=any(e.get('event')=='native_trade_builder_result' and e.get('kind')=='sell' and e.get('result')==1 for e in events)
                result['buy_money_quantity_native']=any(e.get('money')==(3560 if args.move_check else 3920) and e.get('items')==(2 if args.move_check else 1) for e in inventory_samples) and any(e.get('quantity')==3 and e.get('name')=='レモングミ' for e in named_items)
                result['sell_money_quantity_native']=any(e.get('money')==(3740 if args.move_check else 4100) and e.get('items')==(2 if args.move_check else 1) for e in inventory_samples) and any(e.get('quantity')==2 and e.get('name')=='レモングミ' for e in named_items)
                sales=[e for e in events if e.get('event')=='native_trade_builder_result' and e.get('kind')=='sell' and e.get('result')==1]
                result['shop_quantity_refreshed_native']=bool(sales) and any(e.get('event')=='native_shop_row_render' and e.get('name')=='レモングミ' and e.get('mode')==1 and e.get('quantity')==2 and e.get('host_time',0)>sales[-1]['host_time'] for e in events)
                result['inventory_window_open_native']=any(e.get('event')=='native_inventory_frame_state' and e.get('visible') is True for e in events)
                if not args.reenter_check and not all(result[k] for k in ('buy_request_built_native','sell_request_built_native','buy_money_quantity_native','sell_money_quantity_native','shop_quantity_refreshed_native')):
                    failure=failure or 'Native purchase 3 / sell 1 / inventory / wallet checks did not all pass'
                if not result['original_lemon_icon_native']:
                    failure=failure or 'Original lemon ICND icon was not supplied to original inventory control'
                if not result['inventory_window_open_native']:
                    failure=failure or 'Actual original inventory frame did not become visible through the mouse button'
                if not args.reenter_check and not all(result[k] for k in ('shop_historical_names_native','shop_historical_prices_native','shop_historical_item_count_native','shop_display_price_text_native')):
                    failure=failure or 'Historical name/price/count were not all observed in original shop controls'
                shown=[e for e in events if e.get('event')=='native_shop_frame_show' and e.get('result')==1]
                visible=[e for e in events if e.get('event')=='native_shop_frame_state' and e.get('visible') is True and shown and e.get('host_time',0)>shown[-1]['host_time']]
                closes=[e for e in events if e.get('event')=='native_shop_frame_state' and e.get('visible') is False and visible and e.get('host_time',0)>visible[0]['host_time']]
                result['shop_closed_native']=bool(closes)
                result['movement_after_shop_close_native']=bool(closes) and bool(positions) and tuple(positions[-1])==grid_to_point(server.positions.load(1,server.characters.list(1)[0]['identity'])['grid']) and tuple(positions[-1])!=expected_position and any(e.get('event')=='native_move_path_request' and e.get('host_time',0)>closes[0]['host_time'] for e in events)
                if not args.reenter_check and (not result['map_entered'] or not result['npc_selected_native'] or not result['shop_catalog_parsed_native'] or not result['shop_frame_shown_native']):
                    failure=failure or 'Original map/NPC selection/shop data/open checks did not all pass'
                if not args.reenter_check and (not result['shop_closed_native'] or not result['movement_after_shop_close_native']):
                    failure=failure or 'Original shop close and subsequent map walking did not both pass'
                if args.reenter_check:
                    result['position_restored_without_movement']=bool(positions) and all(tuple(x)==expected_position for x in positions)
                    if not result['map_entered'] or not result['position_restored_without_movement']:
                        failure=failure or 'Original reentry did not continuously render the saved destination'
                    result['inventory_restored_native']=bool(inventory_samples) and all(e.get('money')==expected_inventory['money'] and e.get('items')==len(expected_inventory['items']) for e in inventory_samples) and all(any(e.get('identity')==list(item['identity']) and e.get('quantity')==item['quantity'] and e.get('name')==item['name'] for e in named_items) for item in expected_inventory['items'])
                    result['vitals_restored_native']=bool(vital_samples) and all(all(e.get(k)==v for k,v in expected_vitals.items()) for e in vital_samples)
                    if args.use_check and not result['vitals_restored_native']:failure=failure or 'Saved HP/TP were not restored in original client'
                    if not expected_inventory['items'] or not result['inventory_restored_native']:
                        failure=failure or 'Original reentry did not restore saved items and funds'
            (out/'runtime_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
            if pid is not None:
                try:device.kill(pid)
                except Exception:pass
            if session is not None:
                try:session.detach()
                except Exception:pass
            server.close();faulthandler.cancel_dump_traceback_later();diagnostic.close()
            for retry in range(30):
                try:exe.unlink(missing_ok=True);break
                except PermissionError:time.sleep(.1)
        if failure:raise RuntimeError(failure)

if __name__=='__main__':main()
