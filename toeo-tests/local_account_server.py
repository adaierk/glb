"""Local account/prelogin plus persistent character creation/list/deletion.

Plain transport is verified through original x86 send/receive code. Compression
or encryption selected by real startup is logged and rejected, never guessed.
"""
import argparse
import hashlib
import hmac
import json
import secrets
import sqlite3
import struct
import threading
from pathlib import Path
from session_bootstrap_server import BootstrapServer
from native_handshake_packets import bootstrap402,user_record
from native_data_packets import FrameStream,parse405,data405
from account_packets import decode_string,message,login_ok_body
from game_login_packets import game_login_reply,native_crc
from character_packets import character_list_reply,select_character_reply
from character_mutation_packets import mutation_reply
from character_store import CharacterStore,CharacterRejected
from world_auth_packets import parse_world_admission,world_admission_ack,parse_world_account,world_account_ack
from world_ticket_store import WorldTicketStore


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
    def __init__(self,out,world_route_probe=False,**kwargs):
        super().__init__(out,**kwargs)
        self.world_route_probe=world_route_probe
        self.accounts=AccountStore(self.out/'local_accounts.sqlite')
        self.characters=CharacterStore(self.accounts)
        self.world_tickets=WorldTicketStore(self.accounts)
        self.accounts_closed=False

    def greeting(self,port):
        # Client sender 610e4d requires registry[0] to be the server user.
        return bootstrap402(port=port,records=[user_record(2,2,1),user_record(1,1,2)])

    def should_greet(self,port):
        return port!=self.world_port

    def close(self):
        super().close()
        if not self.accounts_closed:
            self.accounts.close();self.accounts_closed=True

    def connection_closed(self,conn_id,state):
        self.world_tickets.disconnect(str(conn_id))

    def process_game_bytes(self,c,port,conn_id,data,state):
        stream=state.setdefault('stream',FrameStream())
        for frame in stream.feed(data):
            outer=struct.unpack_from('<H',frame,6)[0]
            if outer!=0x405:
                self.log('unimplemented_control',connection=conn_id,outer=hex(outer),hex=frame.hex())
                continue
            parsed=parse405(frame)
            op,payload,req=parsed['opcode'],parsed['payload'],parsed['request_id']
            self.log('plain_application_request',connection=conn_id,opcode=hex(op),request_id=req)
            if op==4:
                account_id=parse_world_account(payload)
                authenticated=state.get('game_account_id') or state.get('account_id')
                completed=self.world_tickets.complete(account_id,str(conn_id)) if authenticated==account_id else None
                if not completed:
                    self.log('world_account_control_rejected',connection=conn_id,account_id=account_id,
                             note='Requires authenticated matching account and one active admission')
                    continue
                state['world_account_control']=completed
                c.sendall(data405(world_account_ack(req),0,2,1,1))
                self.log('world_account_control_ack',connection=conn_id,request_id=req,**completed)
                continue
            if op==0x3b and self.world_route_probe:
                account_id=state.get('game_account_id')
                if not account_id:
                    self.log('selection_without_game_login',connection=conn_id);continue
                if len(payload)!=24 or struct.unpack_from('<I',payload,20)[0]!=0:
                    self.log('unsupported_selection_request',connection=conn_id);continue
                identity=struct.unpack_from('<II',payload,12)
                cache=state.setdefault('selection_answers',{})
                key=(account_id,req)
                prior=cache.get(key)
                if prior:
                    if prior[0]==payload:c.sendall(data405(prior[1],0,2,1,1))
                    else:self.log('selection_request_id_conflict',connection=conn_id,request_id=req)
                    continue
                try:
                    ticket=self.world_tickets.issue(account_id,identity)
                    # Research endpoint: first DWORD is measured ticket; remaining fields are partial.
                    fields=(ticket,0,*identity,0,0,0,0,0)
                    answer=select_character_reply(fields,[(0x0100007f,45002,self.main_port)],request_id=req)
                    self.log('selection_probe_ticket_issued',connection=conn_id,ticket=ticket,identity=identity,
                             note='Partial research route; UDP and remaining selection fields unresolved')
                except ValueError as error:
                    answer=select_character_reply((0,)*9,[],request_id=req,status=-1)
                    self.log('selection_probe_rejected',connection=conn_id,reason=str(error))
                if len(cache)>=128:cache.pop(next(iter(cache)))
                cache[key]=(payload,answer)
                c.sendall(data405(answer,0,2,1,1));continue
            if op==0x18:
                network_parameter,ticket=parse_world_admission(payload)
                claimed=self.world_tickets.claim(ticket,str(conn_id),state.get('game_account_id'))
                if not claimed:
                    self.log('world_admission_rejected',connection=conn_id,ticket=ticket,
                             note='No valid locally issued ticket; unmeasured world error reply not fabricated')
                    continue
                state['world_admission']=claimed
                c.sendall(data405(world_admission_ack(req),0,2,1,1))
                self.log('world_admission_ack',connection=conn_id,network_parameter=network_parameter,
                         ticket=ticket,request_id=req,**claimed)
                continue
            if op==0x35 and len(payload)==9:
                if not state.get('game_account_id'):
                    self.log('character_query_without_game_login',connection=conn_id)
                    continue
                roles=self.characters.list(state['game_account_id'])
                answer=character_list_reply([r['record'] for r in roles],3-len(roles),request_id=req)
                c.sendall(data405(answer,0,2,1,1))
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
                    c.sendall(data405(prior[1],0,2,1,1))
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
                c.sendall(data405(answer,0,2,1,1))
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
            reply=data405(answer,0,2,1,1)
            c.sendall(reply)
            self.log('send_application_answer',connection=conn_id,opcode=hex(struct.unpack_from('<H',answer,1)[0]),
                     request_id=req,bytes=len(reply),hex=reply.hex())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='local_login_report')
    p.add_argument('--duration',type=int,default=600)
    p.add_argument('--world-route-probe',action='store_true',help='Experimental partial selection route; no map or UDP implementation')
    a=p.parse_args();server=LocalAccountServer(a.out,world_route_probe=a.world_route_probe)
    try:
        server.start()
        print('Local account server: archive001 / local123. Persistent characters enabled; map/world pending.',flush=True)
        server.stop_event.wait(a.duration)
    except KeyboardInterrupt:pass
    finally:server.close()
