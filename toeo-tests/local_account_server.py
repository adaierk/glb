"""Local account/prelogin plus persistent character creation/list/deletion.

Plain and encrypted transport are verified through original x86 send/receive code.
"""
import argparse
import hashlib
import hmac
import json
import secrets
import sqlite3
import struct
import threading
import time
from pathlib import Path
from session_bootstrap_server import BootstrapServer
from native_handshake_packets import bootstrap402,user_record
from native_data_packets import FrameStream,parse405,data405
from native_cipher import encode as encrypt
from account_packets import decode_string,message,login_ok_body
from game_login_packets import game_login_reply,native_crc
from character_packets import character_list_reply,select_character_reply
from character_mutation_packets import mutation_reply
from character_store import CharacterStore,CharacterRejected
from world_auth_packets import parse_world_admission,world_admission_ack,parse_world_account,world_account_ack
from world_ticket_store import WorldTicketStore
from world_endpoint_packets import parse_endpoint_request,endpoint_reply,parse_endpoint_attachment
from world_map_packets import LOCAL_MAP_ID,world_initialization_reply,world_map_ready_reply
from world_movement_packets import parse_move_request,move_reply,move_rejection_reply
from world_npc_packets import (shop_actor_notice,SHOP_IDENTITY,SHOP_GRID,parse_npc_request,
                               npc_selection_reply,npc_action_reply,shop_open_notice)
from world_position_store import WorldPositionStore,walkable_grid
from world_inventory_store import WorldInventoryStore,TradeRejected
from world_inventory_packets import parse_trade_request,parse_shop_close_request,parse_item_move_request,transaction_reply,inventory_notice
from world_equipment_visual_packets import equipment_visual_notice
from world_item_use_packets import parse_item_use_request,vitals_notice
from world_item_source_packets import parse_item_source_request,item_source_reply
from native_map_geometry import grid_to_point


class AccountStore:
    def __init__(self,path):
        self.lock=threading.Lock()
        self.db=sqlite3.connect(str(path),check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY, username TEXT UNIQUE, salt BLOB, hash BLOB)')
        self.db.execute('CREATE TABLE IF NOT EXISTS sessions(sid INTEGER PRIMARY KEY, account_id INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP)')
        self.db.commit()
        self.add('archive001','local123')

    def add(self,username,password):
        salt=secrets.token_bytes(16)
        hashed=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,100000)
        with self.lock:
            self.db.execute('INSERT OR IGNORE INTO accounts(username,salt,hash) VALUES(?,?,?)',(username,salt,hashed))
            self.db.commit()

    def authenticate(self,username,password):
        # Original GUI appends this exact historical realm before opcode 0x20.
        if username.endswith('@toeo.isao.net'):
            username=username[:-len('@toeo.isao.net')]
        with self.lock:
            row=self.db.execute('SELECT id,salt,hash FROM accounts WHERE username=?',(username,)).fetchone()
        if row is None:return None
        hashed=hashlib.pbkdf2_hmac('sha256',password.encode(),row[1],100000)
        return row[0] if hmac.compare_digest(hashed,row[2]) else None

    def new_session(self,account_id):
        with self.lock:
            while True:
                sid=secrets.randbelow(0xfffffffe)+1
                try:
                    self.db.execute('INSERT INTO sessions(sid,account_id) VALUES(?,?)',(sid,account_id));break
                except sqlite3.IntegrityError:continue
            self.db.commit()
        return sid

    def close(self):
        with self.lock:self.db.close()


class LocalAccountServer(BootstrapServer):
    def __init__(self,out,world_route_probe=False,account_database=None,shop_preview=False,world_profile='forest',combat_preview=False,**kwargs):
        super().__init__(out,**kwargs)
        self.world_route_probe=world_route_probe
        from world_profiles import world_profile as get_world_profile
        self.profile=get_world_profile(world_profile)
        self.combat_preview=combat_preview
        self.map_id=self.profile.map_id
        self.shop_grid=self.profile.merchant_grid
        self.shop_preview=shop_preview or self.profile.stock_key is not None
        self.accounts=AccountStore(Path(account_database) if account_database else self.out/'local_accounts.sqlite')
        self.characters=CharacterStore(self.accounts)
        self.positions=WorldPositionStore(self.accounts,self.profile)
        self.inventory=WorldInventoryStore(self.accounts)
        self.world_tickets=WorldTicketStore(self.accounts)
        self.accounts_closed=False
        self.endpoint_lock=threading.Lock()
        self.endpoint_routes={}

    def greeting(self,port):
        # Client sender 610e4d requires registry[0] to be the server user.
        server_uid,client_uid=(4,3) if port==11101 else (2,1)
        return bootstrap402(port=port,records=[user_record(2,server_uid,1),user_record(1,client_uid,2)])

    def should_greet(self,port):
        return port!=self.world_port

    def close(self):
        super().close()
        if not self.accounts_closed:
            self.accounts.close();self.accounts_closed=True

    def connection_closed(self,conn_id,state):
        self.world_tickets.disconnect(str(conn_id))

    def send_answer(self,c,payload,state):
        c.sendall(data405(encrypt(payload) if state.get('encrypted') else payload,0,
                         state.get('server_uid',2),1,state.get('client_uid',1)))

    def process_game_bytes(self,c,port,conn_id,data,state):
        state.setdefault('server_uid',4 if port==11101 else 2)
        state.setdefault('client_uid',3 if port==11101 else 1)
        stream=state.setdefault('stream',FrameStream())
        for frame in stream.feed(data):
            outer=struct.unpack_from('<H',frame,6)[0]
            if outer==0x406:
                notification=bytearray(36)
                notification[:4]=frame[:4]
                struct.pack_into('<HHHH',notification,4,36,0x406,31,0)
                struct.pack_into('<I',notification,14,state['server_uid'])
                struct.pack_into('<IHB',notification,24,state['server_uid'],0,1)
                notification[31:35]=frame[:4]
                c.sendall(notification)
                self.log('server_receive_ready406',connection=conn_id,hex=notification.hex())
                continue
            if outer!=0x405:
                self.log('unimplemented_control',connection=conn_id,outer=hex(outer),hex=frame.hex())
                continue
            parsed=parse405(frame)
            state['encrypted']=parsed['encrypted']
            op,payload,req=parsed['opcode'],parsed['payload'],parsed['request_id']
            self.log('application_request',connection=conn_id,opcode=hex(op),request_id=req,encrypted=state['encrypted'])
            if op==0x0d and self.world_route_probe:
                endpoint,ticket=parse_endpoint_request(payload)
                account_id=state.get('game_account_id')
                with self.accounts.lock:
                    row=self.accounts.db.execute('''SELECT t.account_id,t.character_id FROM world_tickets t
                        JOIN characters c ON c.id=t.character_id AND c.account_id=t.account_id
                        WHERE ticket=? AND expires>?''',(ticket,time.time())).fetchone()
                if not row or row[0]!=account_id:
                    self.log('world_endpoint_ticket_rejected',connection=conn_id,ticket=ticket);continue
                with self.endpoint_lock:
                    self.endpoint_routes[3]=dict(account_id=account_id,ticket=ticket,
                                                network_parameter=11101,version=1)
                self.send_answer(c,message(0x0e,b'',req),state)
                answer=endpoint_reply(endpoint,11101,11101,3,1,0x123abc,0x0100007f,req)
                self.send_answer(c,answer,state)
                self.log('world_endpoint_assigned',connection=conn_id,ticket=ticket,uid=3,
                         endpoint_hex=endpoint.hex(),answer_hex=answer.hex(),tcp_port=11101)
                continue
            if op==0x10 and self.world_route_probe:
                status,parameter,version,uid=parse_endpoint_attachment(payload)
                with self.endpoint_lock:route=self.endpoint_routes.get(uid)
                if port!=self.main_port or not route or state.get('game_account_id')!=route['account_id'] or status!=0 or \
                        (parameter,version)!=(route['network_parameter'],route['version']):
                    self.log('world_endpoint_attachment_rejected',connection=conn_id,uid=uid,status=status);continue
                with self.endpoint_lock:route['attached']=True
                state['world_endpoint_ticket']=route['ticket']
                self.send_answer(c,message(0x11,b'',req),state)
                self.log('world_endpoint_attachment_ack',connection=conn_id,uid=uid,**route)
                continue
            if op==0x14 and len(payload)==9:
                if not state.get('game_account_id'):
                    self.log('world_relogin_without_game_login',connection=conn_id);continue
                self.send_answer(c,message(0x15,b'',req),state)
                self.log('world_relogin_ack',connection=conn_id,request_id=req)
                continue
            if op==4:
                account_id=parse_world_account(payload)
                authenticated=state.get('game_account_id') or state.get('account_id')
                if port==11101:
                    with self.endpoint_lock:route=self.endpoint_routes.get(state['client_uid'])
                    if route and route.get('attached'):authenticated=route['account_id']
                completed=self.world_tickets.complete(account_id,str(conn_id)) if authenticated==account_id else None
                if not completed:
                    self.log('world_account_control_rejected',connection=conn_id,account_id=account_id,
                             note='Requires authenticated matching account and one active admission')
                    continue
                state['world_account_control']=completed
                state['game_account_id']=account_id
                self.send_answer(c,world_account_ack(req),state)
                self.log('world_account_control_ack',connection=conn_id,request_id=req,**completed)
                continue
            if op==0x3b and self.world_route_probe:
                account_id=state.get('game_account_id')
                if not account_id:
                    self.log('selection_without_game_login',connection=conn_id);continue
                if len(payload)!=24 or struct.unpack_from('<I',payload,20)[0]&~0x0e:
                    self.log('unsupported_selection_request',connection=conn_id);continue
                identity=struct.unpack_from('<II',payload,12)
                cache=state.setdefault('selection_answers',{})
                key=(account_id,req)
                prior=cache.get(key)
                if prior:
                    if prior[0]==payload:self.send_answer(c,prior[1],state)
                    else:self.log('selection_request_id_conflict',connection=conn_id,request_id=req)
                    continue
                try:
                    ticket=self.world_tickets.issue(account_id,identity)
                    # Research endpoint: first DWORD is measured ticket; remaining fields are partial.
                    fields=(ticket,self.map_id,*identity,0,0,0,0,0)
                    answer=select_character_reply(fields,[(0x0100007f,45002,self.main_port)],request_id=req)
                    self.log('selection_probe_ticket_issued',connection=conn_id,ticket=ticket,identity=identity,
                             note='Partial research route; UDP and remaining selection fields unresolved')
                except ValueError as error:
                    answer=select_character_reply((0,)*9,[],request_id=req,status=-1)
                    self.log('selection_probe_rejected',connection=conn_id,reason=str(error))
                if len(cache)>=128:cache.pop(next(iter(cache)))
                cache[key]=(payload,answer)
                self.send_answer(c,answer,state);continue
            if op==0x18:
                network_parameter,ticket=parse_world_admission(payload)
                claimed=self.world_tickets.claim(ticket,str(conn_id),state.get('game_account_id'))
                if not claimed:
                    self.log('world_admission_rejected',connection=conn_id,ticket=ticket,
                             note='No valid locally issued ticket; unmeasured world error reply not fabricated')
                    continue
                state['world_admission']=claimed
                self.send_answer(c,world_admission_ack(req),state)
                self.log('world_admission_ack',connection=conn_id,network_parameter=network_parameter,
                         ticket=ticket,request_id=req,**claimed)
                continue
            if op==0x33 and len(payload)==56 and self.world_route_probe:
                control=state.get('world_account_control')
                if not control or port!=11101:
                    self.log('map_query_without_world_control',connection=conn_id);continue
                if struct.unpack_from('<I',payload,12)[0]!=native_crc(payload[16:]):
                    raise ValueError('World initialization query CRC mismatch')
                roles=self.characters.list(control['account_id'])
                role=next((r for r in roles if r['identity']==tuple(control['character_id'])),None)
                if role is None:
                    self.log('map_query_character_missing',connection=conn_id);continue
                position=self.positions.load(control['account_id'],role['identity'])
                inventory=self.inventory.load(control['account_id'],role['identity'])
                answer=world_initialization_reply(role['identity'],role['name'],role['native_fields'],req,
                    map_id=position['map_id'],position=grid_to_point(position['grid']),label=self.profile.label,inventory=inventory,
                    vitals=self.inventory.load_vitals(control['account_id'],role['identity']))
                self.send_answer(c,answer,state)
                state['world_grid']=position['grid']
                self.log('map_initialization_candidate_sent',connection=conn_id,request_id=req,
                         map_id=self.map_id,character_id=role['identity'],bytes=len(answer),
                         grid=position['grid'],restored=position['restored'],request_hex=payload.hex())
                self.log('world_inventory_restored',connection=conn_id,identity=role['identity'],**inventory)
                continue
            if op==0x39 and len(payload)==40 and port==11101:
                control=state.get('world_account_control')
                identity=struct.unpack_from('<II',payload,24)
                if not control or identity!=tuple(control['character_id']):
                    self.log('world_map_ready_rejected',connection=conn_id,identity=identity);continue
                ready_answer=world_map_ready_reply(req,self.map_id,self.profile.navigation)
                self.send_answer(c,ready_answer,state)
                state['world_map_ready']=True
                self.log('world_map_ready_answer',connection=conn_id,request_id=req,
                         map_id=self.map_id,identity=identity,bytes=len(ready_answer))
                if not state.get('local_shop_announced'):
                    notice=shop_actor_notice(self.profile)
                    self.send_answer(c,notice,state)
                    state['local_shop_announced']=True
                    self.log('local_shop_actor_announced',connection=conn_id,identity=SHOP_IDENTITY,
                             grid=self.shop_grid,map_id=self.map_id,bytes=len(notice))
                if self.combat_preview and not state.get('local_enemy_announced'):
                    from world_enemy_packets import enemy_actor_notice,enemy_grid,ENEMY_IDENTITY
                    notice=enemy_actor_notice(self.profile)
                    self.send_answer(c,notice,state)
                    state['local_enemy_announced']=True
                    self.log('local_enemy_actor_announced',connection=conn_id,identity=ENEMY_IDENTITY,
                             grid=enemy_grid(self.profile),map_id=self.map_id,
                             provenance='Original SLIME CID0 ID1200 and field resource; explicit local HP and placement')
                continue
            if op==0x4e and port==11101:
                from world_npc_packets import actor_target_reply
                control=state.get('world_account_control')
                try:target=parse_npc_request(payload)
                except ValueError as error:
                    self.log('actor_target_rejected',connection=conn_id,reason=str(error));continue
                if not control or not state.get('world_map_ready') or target['identity']!=tuple(control['character_id']) or target['map_id']!=self.map_id or target['group']!=((state.get('local_battle_group') or (0,0)) if self.combat_preview else (0,0)) or target['target'] not in ((0,0),SHOP_IDENTITY,tuple(control['character_id'])) and not (self.combat_preview and state.get('local_enemy_announced') and target['target']==(0x72000001,1)):
                    self.log('actor_target_rejected',connection=conn_id,reason='Character, ready map, group or target mismatch');continue
                answer=actor_target_reply(target)
                self.send_answer(c,answer,state)
                if target['group']!=(0,0):state['local_battle_target']=target['target']
                self.log('actor_target_answer',connection=conn_id,request_hex=payload.hex(),answer_hex=answer.hex(),**target)
                continue
            if op in (0xc6,0xc8) and port==11101:
                control=state.get('world_account_control')
                try:npc=parse_npc_request(payload)
                except ValueError as error:
                    self.log('npc_request_rejected',connection=conn_id,reason=str(error));continue
                is_enemy=self.combat_preview and state.get('local_enemy_announced') and npc['target']==(0x72000001,1)
                if not control or not state.get('world_map_ready') or npc['identity']!=tuple(control['character_id']) or npc['map_id']!=self.map_id or not (npc['target']==SHOP_IDENTITY or is_enemy):
                    self.log('npc_request_rejected',connection=conn_id,reason='Character, ready map or target mismatch');continue
                self.log('native_npc_request',connection=conn_id,request_hex=payload.hex(),**npc)
                if is_enemy:
                    from world_enemy_packets import ENEMY_IDENTITY,enemy_grid
                    from world_combat_packets import enemy_selection_reply,enemy_action_reply,encounter_notice,BATTLE_GROUP
                    if state.get('local_battle_group'):
                        self.log('enemy_request_rejected',connection=conn_id,reason='Encounter already active');continue
                    if op==0xc6:
                        if npc['grid']!=enemy_grid(self.profile):
                            self.log('enemy_request_rejected',connection=conn_id,reason='Enemy grid mismatch');continue
                        state['enemy_selected']=ENEMY_IDENTITY
                        answer=enemy_selection_reply(npc,self.profile)
                        self.send_answer(c,answer,state)
                        self.log('enemy_selection_answer',connection=conn_id,request_id=req,answer_hex=answer.hex())
                    elif npc['action']==1 and state.get('enemy_selected')==ENEMY_IDENTITY:
                        roles=self.characters.list(control['account_id'])
                        role=next((r for r in roles if r['identity']==tuple(control['character_id'])),None)
                        if role is None:
                            self.log('enemy_request_rejected',connection=conn_id,reason='Selected character missing');continue
                        self.send_answer(c,enemy_action_reply(npc),state)
                        notice_id=0x73001001
                        notice=encounter_notice(role['identity'],role['name'],role['native_fields'],self.profile,notice_id,background_id=15,
                            vitals=self.inventory.load_vitals(control['account_id'],role['identity']),
                            equipment=self.inventory.load(control['account_id'],role['identity']).get('equipment',[]))
                        state['local_battle_group']=BATTLE_GROUP
                        state['local_encounter_notice_id']=notice_id
                        self.send_answer(c,notice,state)
                        self.log('local_encounter_notice_sent',connection=conn_id,group=BATTLE_GROUP,background_id=15,
                                 request_id=notice_id,notice_hex=notice.hex(),
                                 provenance='Explicit offline SLIME encounter; original BBg0015 asset, local arena and stats')
                    else:self.log('enemy_request_rejected',connection=conn_id,reason='Unsupported or unselected enemy action')
                    continue
                if op==0xc6:
                    if npc['grid']!=self.shop_grid:
                        self.log('npc_request_rejected',connection=conn_id,reason='NPC grid mismatch');continue
                    state['npc_selected']=SHOP_IDENTITY
                    answer=npc_selection_reply(npc,self.profile)
                    self.send_answer(c,answer,state)
                    self.log('npc_selection_answer',connection=conn_id,request_id=req,answer_hex=answer.hex())
                elif npc['action']==2 and state.get('npc_selected')==SHOP_IDENTITY:
                    self.send_answer(c,npc_action_reply(npc),state)
                    notice_id=state.get('shop_notice_sequence',0)+1;state['shop_notice_sequence']=notice_id
                    if self.shop_preview:
                        from world_shop_catalog import historical_stock,PREVIEW_SOURCE_KEY
                        source=historical_stock(self.profile.stock_key or PREVIEW_SOURCE_KEY)
                        notice=shop_open_notice(npc['identity'],0x70000000+notice_id,stock=source['stock'],map_id=self.map_id)
                    else:
                        notice=shop_open_notice(npc['identity'],0x70000000+notice_id,map_id=self.map_id)
                    self.send_answer(c,notice,state)
                    state['shop_open_notice_id']=0x70000000+notice_id
                    self.log('shop_historical_preview_sent' if self.shop_preview else 'shop_empty_catalog_sent',connection=conn_id,request_id=state['shop_open_notice_id'],notice_hex=notice.hex(),
                             **({'source_url':source['source_url'],'historical_area':source['area'],'historical_xy':source['source_xy'],'stock_count':len(source['stock']),
                                 'placement_basis': 'Original minimap/Wiki visual match plus Wiki XY' if self.profile.stock_key else 'Local diagnostic placement',
                                 'world_profile':self.profile.key,'merchant_grid':self.shop_grid,'native_templates_and_icons_verified':False} if self.shop_preview else {}))
                else:self.log('npc_request_rejected',connection=conn_id,reason='Unsupported or unselected NPC action')
                continue
            if op==0x9f and port==11101 and self.combat_preview:
                control=state.get('world_account_control')
                expected=(*control['character_id'],self.map_id,*state['local_battle_group']) if control and state.get('local_battle_group') else None
                if len(payload)!=32 or expected is None or not state.get('local_encounter_ack') or struct.unpack_from('<5I',payload,12)!=expected:
                    self.log('battle_resource_request_rejected',connection=conn_id,request_hex=payload.hex());continue
                # Original52C8E7 A0 handler completes only the native pending request522260.
                answer=message(0xa0,bytes(3)+struct.pack('<5I',*expected),req)
                self.send_answer(c,answer,state)
                self.log('battle_resource_reply_sent',connection=conn_id,request_id=req,request_hex=payload.hex(),answer_hex=answer.hex())
                if not state.get('local_battle_started'):
                    from world_battle_commands import battle_start_notice
                    notice=battle_start_notice(self.map_id,state['local_battle_group'],0x73001002)
                    self.send_answer(c,notice,state)
                    state['local_battle_started']=True
                    self.log('battle_start_notice_sent',connection=conn_id,answer_hex=notice.hex())
                continue
            if op==0xa8 and port==11101 and self.combat_preview:
                from world_battle_commands import parse_attack_request,validate_attack_request
                control=state.get('world_account_control')
                try:
                    attack=parse_attack_request(payload)
                    if not control or not state.get('local_battle_started'):raise ValueError('No active battle')
                    validate_attack_request(attack,control['character_id'],self.map_id,state['local_battle_group'],state.get('local_battle_target'))
                except ValueError as error:
                    self.log('battle_attack_rejected',connection=conn_id,reason=str(error),request_hex=payload.hex());continue
                self.log('battle_attack_request_native',connection=conn_id,request_hex=payload.hex(),**attack)
                continue
            if op==0x9e and port==11101 and self.combat_preview:
                control=state.get('world_account_control')
                expected=(*control['character_id'],self.map_id,*state['local_battle_group']) if control and state.get('local_battle_group') else None
                if len(payload)!=32 or expected is None or req!=state.get('local_encounter_notice_id') or struct.unpack_from('<5I',payload,12)!=expected:
                    self.log('encounter_ack_rejected',connection=conn_id,request_hex=payload.hex());continue
                state['local_encounter_ack']=True
                self.log('encounter_ack_native',connection=conn_id,request_id=req,group=state['local_battle_group'],request_hex=payload.hex())
                continue
            if op==0xd7 and port==11101:
                control=state.get('world_account_control')
                if len(payload)!=36 or not control or req!=state.get('shop_open_notice_id') or struct.unpack_from('<IIIII',payload,12)!=(*control['character_id'],self.map_id,*SHOP_IDENTITY):
                    self.log('shop_catalog_ack_rejected',connection=conn_id,request_hex=payload.hex());continue
                state['shop_catalog_ack_observed']=True
                self.log('shop_catalog_ack_native',connection=conn_id,request_id=req,request_hex=payload.hex())
                continue
            if op in (0xde,0xdf) and port==11101:
                control=state.get('world_account_control')
                try:trade=parse_trade_request(payload)
                except ValueError as error:
                    self.log('shop_trade_malformed',connection=conn_id,reason=str(error),request_hex=payload.hex());continue
                if not control or not state.get('world_map_ready') or trade['identity']!=tuple(control['character_id']) or trade['map_id']!=self.map_id or trade['merchant']!=SHOP_IDENTITY or state.get('npc_selected')!=SHOP_IDENTITY or not state.get('shop_catalog_ack_observed') or not self.shop_preview:
                    self.log('shop_trade_unauthorized',connection=conn_id,reason='Character, map or selected catalog mismatch');continue
                from world_shop_catalog import historical_stock,PREVIEW_SOURCE_KEY
                source=historical_stock(self.profile.stock_key or PREVIEW_SOURCE_KEY)
                state.setdefault('trade_connection_key',secrets.token_hex(16))
                status=0;reason=None;replayed=False
                try:
                    inventory,replayed=self.inventory.trade(control['account_id'],trade['identity'],source,trade,payload,state['trade_connection_key'])
                except TradeRejected as error:
                    status=-1;reason=str(error)
                    inventory=self.inventory.load(control['account_id'],trade['identity'])
                if replayed:
                    # The receipt is idempotent; a full snapshot must reflect
                    # today's saved state, even after newer transactions.
                    inventory=self.inventory.load(control['account_id'],trade['identity'])
                present={tuple(item['identity']) for item in inventory['items']}
                removed=[line['identity'] for line in trade['lines'] if trade['opcode']==0xdf and tuple(line['identity']) not in present]
                answer=transaction_reply(trade['sequence'],inventory['money'],status,request_id=trade['request_id'],
                                         snapshot=inventory if status==0 else None,removed=removed)
                notice=inventory_notice(trade['identity'],self.map_id,inventory)
                self.send_answer(c,answer,state);self.send_answer(c,notice,state)
                self.log('shop_trade_rejected' if status else 'shop_trade_committed',connection=conn_id,
                         **trade,replayed=replayed,status=status,reason=reason,request_hex=payload.hex(),
                         answer_hex=answer.hex(),inventory_notice_hex=notice.hex(),snapshot=inventory,
                         rules='Local initial grant 5000 / stack 20 / bag 32 / resale half; official values unresolved')
                continue
            if op==0xe0 and port==11101:
                control=state.get('world_account_control')
                try:
                    close=parse_shop_close_request(payload)
                    replayed=state.get('shop_close_command_seen')==payload
                    if not control or not state.get('world_map_ready') or close['identity']!=tuple(control['character_id']) or close['map_id']!=self.map_id or close['merchant']!=SHOP_IDENTITY or not self.shop_preview or (not state.get('shop_catalog_ack_observed') and not replayed):
                        raise ValueError('Unauthorized shop close command')
                except ValueError as error:
                    self.log('shop_close_command_rejected',connection=conn_id,reason=str(error));continue
                inventory=self.inventory.load(control['account_id'],close['identity'])
                answer=transaction_reply(close['sequence'],inventory['money'],request_id=close['request_id'])
                self.send_answer(c,answer,state)
                if not replayed:
                    state['shop_catalog_ack_observed']=False
                    state['shop_close_command_seen']=payload
                self.log('shop_close_command_ack',connection=conn_id,**close,replayed=replayed,answer_hex=answer.hex())
                continue
            if op==0xed and port==11101:
                control=state.get('world_account_control')
                try:
                    source_request=parse_item_source_request(payload)
                    if not control or not state.get('world_map_ready') or source_request['identity']!=tuple(control['character_id']) or source_request['map_id']!=self.map_id:
                        raise ValueError('Unauthorized item-source request')
                    from world_shop_catalog import historical_stock,PREVIEW_SOURCE_KEY
                    stock=historical_stock(self.profile.stock_key or PREVIEW_SOURCE_KEY)['stock']
                    answer=item_source_reply(source_request,stock)
                except ValueError as error:
                    self.log('item_source_rejected',connection=conn_id,reason=str(error));continue
                self.send_answer(c,answer,state)
                self.log('item_source_sent',connection=conn_id,**source_request,compressed=parsed['compressed'],answer_hex=answer.hex())
                continue
            if op==0x54 and port==11101:
                control=state.get('world_account_control')
                try:move=parse_item_move_request(payload)
                except ValueError as error:
                    self.log('item_move_malformed',connection=conn_id,reason=str(error));continue
                if not control or not state.get('world_map_ready') or move['identity']!=tuple(control['character_id']) or move['map_id']!=self.map_id:
                    self.log('item_move_unauthorized',connection=conn_id);continue
                state.setdefault('trade_connection_key',secrets.token_hex(16))
                status=0;reason=None;replayed=False
                try:inventory,replayed=self.inventory.move(control['account_id'],move['identity'],move,payload,state['trade_connection_key'])
                except TradeRejected as error:
                    status=-1;reason=str(error);inventory=self.inventory.load(control['account_id'],move['identity'])
                answer=transaction_reply(move['sequence'],inventory['money'],status,request_id=move['request_id'],snapshot=inventory if status==0 else None)
                self.send_answer(c,answer,state)
                if status==0:
                    self.send_answer(c,inventory_notice(move['identity'],self.map_id,inventory),state)
                    if 4 in (move['source_location'],move['destination_location']):
                        self.send_answer(c,equipment_visual_notice(move['identity'],self.map_id,inventory),state)
                        self.send_answer(c,vitals_notice(move['identity'],self.map_id,self.inventory.load_vitals(control['account_id'],move['identity'])),state)
                self.log('item_move_rejected' if status else 'item_move_committed',connection=conn_id,**move,status=status,reason=reason,replayed=replayed,snapshot=inventory,request_hex=payload.hex(),answer_hex=answer.hex())
                continue
            if op==0x55 and port==11101:
                control=state.get('world_account_control')
                try:use=parse_item_use_request(payload)
                except ValueError as error:
                    self.log('item_use_malformed',connection=conn_id,reason=str(error),request_hex=payload.hex());continue
                if not control or not state.get('world_map_ready') or use['identity']!=tuple(control['character_id']) or use['map_id']!=self.map_id:
                    self.log('item_use_unauthorized',connection=conn_id,reason='Character or ready map mismatch');continue
                state.setdefault('trade_connection_key',secrets.token_hex(16))
                status=0;reason=None;replayed=False
                try:
                    inventory,vitals,replayed=self.inventory.use(control['account_id'],use['identity'],use,payload,state['trade_connection_key'])
                except TradeRejected as error:
                    status=-1;reason=str(error)
                    inventory=self.inventory.load(control['account_id'],use['identity'])
                    vitals=self.inventory.load_vitals(control['account_id'],use['identity'])
                present={tuple(x['identity']) for x in inventory['items']}
                removed=() if use['item'] in present or status else (use['item'],)
                answer=transaction_reply(use['sequence'],inventory['money'],status,request_id=use['request_id'],
                    snapshot=inventory if status==0 else None,removed=removed)
                self.send_answer(c,answer,state)
                if status==0:
                    self.send_answer(c,inventory_notice(use['identity'],self.map_id,inventory),state)
                    self.send_answer(c,vitals_notice(use['identity'],self.map_id,vitals),state)
                self.log('item_use_rejected' if status else 'item_use_committed',connection=conn_id,
                    **use,status=status,reason=reason,replayed=replayed,snapshot=inventory,vitals=vitals,
                    request_hex=payload.hex(),answer_hex=answer.hex(),
                    limitation='Historical recovery amounts; casting, interrupted use and battle targeting still pending')
                continue
            if op==0x42 and port==11101:
                control=state.get('world_account_control')
                try:move=parse_move_request(payload,self.profile)
                except ValueError as error:
                    self.log('world_move_rejected',connection=conn_id,reason=str(error));continue
                if not control or not state.get('world_map_ready') or move['identity']!=tuple(control['character_id']) or move['map_id']!=self.map_id:
                    self.log('world_move_rejected',connection=conn_id,reason='Character or ready map mismatch');continue
                cache=state.setdefault('movement_answers',{})
                previous=cache.get(req)
                if previous:
                    if previous[0]==payload:self.send_answer(c,previous[1],state)
                    else:self.log('world_move_rejected',connection=conn_id,reason='Conflicting movement request id')
                    continue
                if not self.profile.walkable(move['target']):
                    grid=self.positions.load(control['account_id'],move['identity'])['grid']
                    answer=move_rejection_reply(move,grid)
                    if len(cache)>=128:cache.pop(next(iter(cache)))
                    cache[req]=(payload,answer)
                    self.send_answer(c,answer,state)
                    self.log('world_move_rejected_and_restored',connection=conn_id,reason='Destination blocked by local navigation',
                             rejected_grid=move['target'],restored_grid=grid,request_id=req,status=-93)
                    continue
                answer=move_reply(move)
                try:self.positions.save(control['account_id'],move['identity'],move['map_id'],move['target'])
                except ValueError as error:
                    self.log('world_move_rejected',connection=conn_id,reason=str(error));continue
                if len(cache)>=128:cache.pop(next(iter(cache)))
                cache[req]=(payload,answer)
                self.send_answer(c,answer,state)
                state['world_grid']=move['target']
                self.log('world_move_ack',connection=conn_id,**move)
                self.log('world_destination_saved',connection=conn_id,identity=move['identity'],map_id=move['map_id'],grid=move['target'])
                continue
            if op==0x35 and len(payload)==9:
                if not state.get('game_account_id'):
                    self.log('character_query_without_game_login',connection=conn_id)
                    continue
                roles=self.characters.list(state['game_account_id'])
                answer=character_list_reply([r['record'] for r in roles],3-len(roles),request_id=req)
                self.send_answer(c,answer,state)
                self.log('send_character_list',connection=conn_id,request_id=req,
                         count=len(roles),available_slots=3-len(roles),
                         note='Recovered core fields; actual model resources and world remain unverified')
                continue
            if op in (0x37,0x39):
                if not state.get('game_account_id'):
                    self.log('character_mutation_without_game_login',connection=conn_id,opcode=hex(op))
                    continue
                cache=state.setdefault('mutation_answers',{})
                key=(state['game_account_id'],op,req)
                prior=cache.get(key)
                if prior and prior[0]==payload:
                    self.send_answer(c,prior[1],state)
                    self.log('repeat_mutation_answer',connection=conn_id,opcode=hex(op),request_id=req)
                    continue
                identity=None;status=0;reason=None
                try:
                    if op==0x37:
                        identity=self.characters.create(state['game_account_id'],payload)
                    else:
                        if len(payload)!=20:raise CharacterRejected('Unexpected deletion packet size')
                        identity=struct.unpack_from('<II',payload,12)
                        self.characters.delete(state['game_account_id'],identity)
                except (ValueError,UnicodeError) as exc:
                    # Original mutation handlers accept 0/1 and reject negative values.
                    # -1 is a generic measured rejection, not a recovered UI-specific error code.
                    status=-1;reason=str(exc)
                answer=mutation_reply(op+1,req,status)
                # Bounded per-connection retransmission cache; request IDs are assigned by original code.
                if len(cache)>=128:cache.pop(next(iter(cache)))
                cache[key]=(payload,answer)
                self.send_answer(c,answer,state)
                event=('character_created' if op==0x37 else 'character_deleted') if status==0 else 'character_mutation_rejected'
                self.log(event,connection=conn_id,
                         account_id=state['game_account_id'],identity=identity,status=status,reason=reason,
                         request_id=req)
                continue
            username=password=None
            if op==0x20 and len(payload)==149:
                username=decode_string(payload[9:79]);password=decode_string(payload[79:149])
            elif op==0x33 and len(payload)==176:
                if struct.unpack_from('<I',payload,12)[0]!=native_crc(payload[16:]):
                    raise ValueError('Game prelogin CRC mismatch')
                if struct.unpack_from('<HH',payload,16)!=(176,97):
                    raise ValueError('Unexpected prelogin request/answer sizes')
                username=decode_string(payload[32:102]);password=decode_string(payload[102:172])
            else:
                self.log('unimplemented_application',connection=conn_id,opcode=hex(op),
                         request_id=req,bytes=len(payload),hex=payload.hex())
                continue
            account_id=self.accounts.authenticate(username,password)
            if account_id is None:
                # Error-code mapping is not yet measured; do not send guessed notices.
                self.log('local_credentials_rejected',connection=conn_id,opcode=hex(op))
                continue
            if op==0x20:
                state['account_id']=account_id
                sid=self.accounts.new_session(account_id)
                answer=message(0x21,login_ok_body(1,account_id,sid,username),req)
                self.log('local_account_accepted',connection=conn_id,account_id=account_id,sid=sid)
            else:
                answer=game_login_reply(username,1,account_id,req)
                state['game_account_id']=account_id
                self.log('game_prelogin_candidate',connection=conn_id,account_id=account_id,
                         note='Native receive/filter/correlator and core identity checks verified')
            reply=data405(encrypt(answer) if state.get('encrypted') else answer,0,2,1,1)
            c.sendall(reply)
            self.log('send_application_answer',connection=conn_id,opcode=hex(struct.unpack_from('<H',answer,1)[0]),
                     request_id=req,bytes=len(reply),hex=reply.hex())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='local_login_report')
    p.add_argument('--duration',type=int,default=600)
    p.add_argument('--world-route-probe',action='store_true',help='Experimental partial selection route; no map or UDP implementation')
    p.add_argument('--shop-preview',action='store_true',help='Display sourced historical stock on the explicitly local diagnostic merchant; placement/templates/icons not recovered')
    a=p.parse_args();server=LocalAccountServer(a.out,world_route_probe=a.world_route_probe,shop_preview=a.shop_preview)
    try:
        server.start()
        print('Local account server: archive001 / local123. Persistent characters enabled; map/world pending.',flush=True)
        server.stop_event.wait(a.duration)
    except KeyboardInterrupt:pass
    finally:server.close()
