"""TCP integration with native client packets; x86 path checked by separate emulator."""
import socket
import struct
import tempfile
import time
import unittest
from pathlib import Path
from local_account_server import LocalAccountServer
from account_packets import login_request,message,encode_string,decode_string
from native_data_packets import FrameStream,data405,parse405
from game_login_packets import game_login_request,native_crc
from character_packets import character_list_request,select_character_request
from character_mutation_packets import create_character_request,delete_character_request
from world_auth_packets import world_admission_request,world_account_request


def recv_frame(sock):
    head=b''
    while len(head)<6:
        chunk=sock.recv(6-len(head))
        if not chunk:raise EOFError()
        head+=chunk
    n=struct.unpack_from('<H',head,4)[0]
    while len(head)<n:
        chunk=sock.recv(n-len(head))
        if not chunk:raise EOFError()
        head+=chunk
    return head


class LocalAccountTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=LocalAccountServer(self.temp.name,main_port=0,world_port=0,bind_extra=False)
        self.server.start()
        self.sock=socket.create_connection(('127.0.0.1',self.server.main_port));self.sock.settimeout(.5)
        self.greeting=recv_frame(self.sock)

    def tearDown(self):
        self.sock.close();self.server.close();self.temp.cleanup()

    def exchange(self,p):
        self.sock.sendall(data405(p,1,1,route=0xffef))
        return parse405(recv_frame(self.sock))['payload']

    def authorize(self,username='archive001',password='local123'):
        self.assertEqual(struct.unpack_from('<H',self.exchange(game_login_request(username,password)),1)[0],0x34)

    def mutation_status(self,p):
        return struct.unpack_from('<h',self.exchange(p),10)[0]

    def test_selection_probe_issues_ticket_and_replay_is_stable(self):
        self.server.world_route_probe=True;self.authorize()
        identity=self.server.characters.create(1,create_character_request('RouteHero'))
        request=select_character_request(identity)
        answer=self.exchange(request)
        self.assertEqual((struct.unpack_from('<H',answer,1)[0],len(answer)),(0x3c,112))
        ticket=struct.unpack_from('<I',answer,12)[0];self.assertGreater(ticket,0)
        self.assertEqual(self.exchange(request),answer)
        self.assertEqual(self.server.accounts.db.execute('SELECT COUNT(*) FROM world_tickets').fetchone()[0],1)
        ack=self.exchange(world_admission_request(11100,ticket,72))
        self.assertEqual((struct.unpack_from('<H',ack,1)[0],len(ack)),(0x19,9))

    def test_selection_probe_rejects_foreign_or_missing_character(self):
        self.server.world_route_probe=True;self.authorize()
        for req,identity in enumerate(((123,2),(999999,1)),1):
            request=bytearray(select_character_request(identity));struct.pack_into('<I',request,5,req)
            answer=self.exchange(request)
            self.assertEqual(struct.unpack_from('<h',answer,10)[0],-1)
        self.assertEqual(self.server.accounts.db.execute('SELECT COUNT(*) FROM world_tickets').fetchone()[0],0)

    def test_selection_probe_requires_login_and_is_disabled_by_default(self):
        self.sock.sendall(data405(select_character_request(),1,1,route=0xffef))
        with self.assertRaises(socket.timeout):self.sock.recv(1)
        self.server.world_route_probe=True
        self.sock.sendall(data405(select_character_request(),1,1,route=0xffef))
        with self.assertRaises(socket.timeout):self.sock.recv(1)

    def test_real_endpoint_channel_binds_selected_account_before_world_control(self):
        self.sock.close();self.server.close()
        self.server=LocalAccountServer(self.temp.name,main_port=0,world_port=0,bind_extra=True,world_route_probe=True)
        self.server.start()
        self.sock=socket.create_connection(('127.0.0.1',self.server.main_port));self.sock.settimeout(.5)
        recv_frame(self.sock);self.authorize()
        identity=self.server.characters.create(1,create_character_request('EndpointHero'))
        selected=self.exchange(select_character_request(identity,options=12))
        ticket=struct.unpack_from('<I',selected,12)[0]
        answer=self.exchange(message(0x0d,b'ABCDEF'+struct.pack('<H',ticket),80))
        self.assertEqual(struct.unpack_from('<H',answer,1)[0],0x0e)
        descriptor=parse405(recv_frame(self.sock))['payload']
        self.assertEqual(struct.unpack_from('<I',descriptor,21)[0],3)
        with socket.create_connection(('127.0.0.1',11101)) as world:
            world.settimeout(.5);greeting=recv_frame(world)
            self.assertEqual(struct.unpack_from('<I',greeting,64)[0],3)
            wrong=message(0x10,struct.pack('<BHII',0,11101,1,99),81)
            self.sock.sendall(data405(wrong,1,1,route=0xffef))
            with self.assertRaises(socket.timeout):self.sock.recv(1)
            attach=message(0x10,struct.pack('<BHII',0,11101,1,3),82)
            self.assertEqual(struct.unpack_from('<H',self.exchange(attach),1)[0],0x11)
            self.assertEqual(struct.unpack_from('<H',self.exchange(world_admission_request(11101,ticket,83)),1)[0],0x19)
            world.sendall(data405(world_account_request(1,84),1,3,route=0xffef))
            reply=parse405(recv_frame(world))
            self.assertEqual((reply['opcode'],reply['request_id']),(5,84))
            # Real world 39 is a 40-byte map-ready request, distinct from
            # the selector's 20-byte character-delete request.
            ready=bytearray(message(0x39,bytes(31),85))
            struct.pack_into('<II',ready,24,99,1)
            world.sendall(data405(ready,1,3,route=0xffef))
            with self.assertRaises(socket.timeout):world.recv(1)
            struct.pack_into('<II',ready,24,*identity)
            world.sendall(data405(ready,1,3,route=0xffef))
            answer=parse405(recv_frame(world))['payload']
            self.assertEqual((len(answer),struct.unpack_from('<I',answer,12)[0]),(5300,5300))
            self.assertEqual(struct.unpack_from('<HH',answer,40),(0xa9,1314))
            self.assertEqual((struct.unpack_from('<h',answer,16)[0],struct.unpack_from('<I',answer,36)[0]),(0,0x1110101))
            self.assertEqual(answer[18],1)  # Original movement permission consumer.
            move=bytearray(message(0x42,bytes(59),86))
            struct.pack_into('<I',move,12,1)
            struct.pack_into('<III',move,28,99,1,0x1110101)
            struct.pack_into('<ffhh',move,52,224.,80.,10,8);move[65]=2
            world.sendall(data405(move,1,3,route=0xffef))
            with self.assertRaises(socket.timeout):world.recv(1)
            struct.pack_into('<II',move,28,*identity)
            world.sendall(data405(move,1,3,route=0xffef))
            reply=parse405(recv_frame(world))
            self.assertEqual((reply['opcode'],reply['request_id']),(0x43,86))
            movement_answer=reply['payload']
            self.assertEqual(struct.unpack_from('<hhhh',movement_answer,28),(6,4,10,8))
            self.assertEqual(struct.unpack_from('<f',movement_answer,44)[0],1.5)
            # A retransmission retains the exact correlated response.
            world.sendall(data405(move,1,3,route=0xffef))
            self.assertEqual(parse405(recv_frame(world))['payload'],movement_answer)
            self.assertEqual(self.server.positions.load(1,identity)['grid'],(10,8))
            struct.pack_into('<I',move,5,87)
            struct.pack_into('<hh',move,60,31,7)  # Preserved forest classification.
            world.sendall(data405(move,1,3,route=0xffef))
            with self.assertRaises(socket.timeout):world.recv(1)
            self.assertEqual(self.server.positions.load(1,identity)['grid'],(10,8))
            self.assertEqual(len(self.server.characters.list(1)),1)

    def open_admitted_world(self,ticket):
        world=socket.create_connection(('127.0.0.1',self.server.main_port));world.settimeout(.5)
        recv_frame(world);world.sendall(data405(world_admission_request(11100,ticket,101),1,1,route=0xffef))
        self.assertEqual(parse405(recv_frame(world))['opcode'],0x19)
        return world

    def test_world_control_completes_across_two_connections_and_replays(self):
        self.authorize();identity=self.server.characters.create(1,create_character_request('ControlHero'))
        ticket=self.server.world_tickets.issue(1,identity)
        with self.open_admitted_world(ticket):
            answer=self.exchange(world_account_request(1,103))
            self.assertEqual((struct.unpack_from('<H',answer,1)[0],len(answer)),(5,9))
            self.assertEqual(self.exchange(world_account_request(1,103)),answer)
            self.assertIsNotNone(self.server.accounts.db.execute('SELECT attached_by FROM world_tickets WHERE ticket=?',(ticket,)).fetchone()[0])

    def test_world_control_rejects_unadmitted_or_mismatched_account(self):
        self.authorize();self.sock.sendall(data405(world_account_request(1,104),1,1,route=0xffef))
        with self.assertRaises(socket.timeout):self.sock.recv(1)
        identity=self.server.characters.create(1,create_character_request('MatchHero'));ticket=self.server.world_tickets.issue(1,identity)
        with self.open_admitted_world(ticket):
            self.sock.sendall(data405(world_account_request(2,105),1,1,route=0xffef))
            with self.assertRaises(socket.timeout):self.sock.recv(1)

    def test_world_control_rejects_expiry_deletion_and_closed_admission(self):
        self.authorize();identity=self.server.characters.create(1,create_character_request('CloseHero'))
        ticket=self.server.world_tickets.issue(1,identity)
        with self.open_admitted_world(ticket):
            self.server.accounts.db.execute('UPDATE world_tickets SET expires=0 WHERE ticket=?',(ticket,));self.server.accounts.db.commit()
            self.sock.sendall(data405(world_account_request(1,106),1,1,route=0xffef))
            with self.assertRaises(socket.timeout):self.sock.recv(1)
        ticket=self.server.world_tickets.issue(1,identity)
        with self.open_admitted_world(ticket):pass
        deadline=time.monotonic()+1
        while time.monotonic()<deadline:
            with self.server.accounts.lock:
                remaining=self.server.accounts.db.execute('SELECT COUNT(*) FROM world_tickets WHERE ticket=?',(ticket,)).fetchone()[0]
            if not remaining:break
            time.sleep(.01)
        self.assertEqual(remaining,0)
        self.sock.sendall(data405(world_account_request(1,107),1,1,route=0xffef))
        with self.assertRaises(socket.timeout):self.sock.recv(1)
        self.assertEqual(self.server.accounts.db.execute('SELECT COUNT(*) FROM world_tickets WHERE ticket=?',(ticket,)).fetchone()[0],0)
        ticket=self.server.world_tickets.issue(1,identity)
        with self.open_admitted_world(ticket):
            self.server.characters.delete(1,identity)
            self.sock.sendall(data405(world_account_request(1,108),1,1,route=0xffef))
            with self.assertRaises(socket.timeout):self.sock.recv(1)

    def test_world_control_rejects_ambiguous_multiple_admissions(self):
        self.authorize();identity=self.server.characters.create(1,create_character_request('AmbiguousHero'))
        first=self.server.world_tickets.issue(1,identity);second=self.server.world_tickets.issue(1,identity)
        with self.open_admitted_world(first),self.open_admitted_world(second):
            self.sock.sendall(data405(world_account_request(1,109),1,1,route=0xffef))
            with self.assertRaises(socket.timeout):self.sock.recv(1)

    def test_server_first_self_second(self):
        self.assertEqual(len(self.greeting),84)
        self.assertEqual(struct.unpack_from('<I',self.greeting,20)[0],2)
        self.assertEqual(struct.unpack_from('<I',self.greeting,40)[0],2)
        self.assertEqual(self.greeting[57],1)
        self.assertEqual(struct.unpack_from('<I',self.greeting,60)[0],1)
        self.assertEqual(self.greeting[77],2)

    def test_partial_account_request_and_persistent_session(self):
        request=bytearray(login_request('archive001','local123'));struct.pack_into('<I',request,5,53)
        wire=data405(request,1,1,route=0xffef,target_index=0,target_uid=0)
        self.sock.sendall(wire[:5]);self.sock.sendall(wire[5:37]);self.sock.sendall(wire[37:])
        answer=parse405(recv_frame(self.sock))
        self.assertEqual(answer['opcode'],0x21);self.assertEqual(answer['request_id'],53)
        p=answer['payload'];self.assertEqual(len(p),105)
        self.assertEqual(struct.unpack_from('<III',p,9),(1,1,1))
        account,sid=struct.unpack_from('<II',p,21)
        self.assertEqual(account,1);self.assertNotEqual(sid,0)
        self.assertEqual(decode_string(p[29:99]),'archive001')
        row=self.server.accounts.db.execute('SELECT account_id FROM sessions WHERE sid=?',(sid,)).fetchone()
        self.assertEqual(row,(1,))

    def test_wrong_password_and_unknown_request_are_not_accepted(self):
        p=login_request('archive001','wrong')
        self.sock.sendall(data405(p,1,1,route=0xffef,target_index=0,target_uid=0))
        with self.assertRaises(socket.timeout):self.sock.recv(1)
        self.assertEqual(self.server.accounts.db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],0)
        self.sock.sendall(data405(message(0x99,b'',7),1,1,route=0xffef,target_index=0,target_uid=0))
        with self.assertRaises(socket.timeout):self.sock.recv(1)

    def test_prelogin_candidate_has_identity_uid_and_copy_length(self):
        p=bytearray(game_login_request('archive001','local123'));struct.pack_into('<I',p,5,7)
        self.sock.sendall(data405(p,1,1,route=0xffef,target_index=0,target_uid=0))
        answer=parse405(recv_frame(self.sock))
        self.assertEqual((answer['opcode'],answer['request_id']),(0x34,7))
        p=answer['payload'];self.assertEqual(len(p),97)
        self.assertEqual(struct.unpack_from('<I',p,12)[0],96)
        self.assertEqual(decode_string(p[16:86]),'archive001')
        self.assertEqual(struct.unpack_from('<II',p,88),(1,1))

    def test_stream_coalescing_and_corruption(self):
        p=data405(message(0x99,b'',7),1,1)
        stream=FrameStream();self.assertEqual(stream.feed(p[:9]),[])
        self.assertEqual(stream.feed(p[9:]+p),[p,p])
        with self.assertRaises(ValueError):FrameStream().feed(p[:-1]+b'\x00')
        field=bytearray(encode_string('テスト'));field[4]^=1
        with self.assertRaises(ValueError):decode_string(bytes(field))

    def test_character_list_after_game_login(self):
        self.sock.sendall(data405(game_login_request('archive001','local123'),1,1,route=0xffef))
        self.assertEqual(parse405(recv_frame(self.sock))['opcode'],0x34)
        p=bytearray(character_list_request());struct.pack_into('<I',p,5,42)
        self.sock.sendall(data405(p,1,1,route=0xffef))
        answer=parse405(recv_frame(self.sock))
        self.assertEqual((answer['opcode'],answer['request_id']),(0x36,42))
        self.assertEqual(len(answer['payload']),40)
        self.assertEqual(struct.unpack_from('<III',answer['payload'],12),(40,0,0))
        self.assertEqual(struct.unpack_from('<II',answer['payload'],20),(0,3))

    def test_character_query_requires_game_login(self):
        self.sock.sendall(data405(character_list_request(),1,1,route=0xffef))
        with self.assertRaises(socket.timeout):self.sock.recv(1)

    def test_create_list_name_parameters_and_delete(self):
        self.authorize()
        params=(5,2,1,2,3,4,5,6,7,1)
        self.assertEqual(self.mutation_status(create_character_request('テスト',params,request_id=10)),0)
        roles=self.server.characters.list(1)
        self.assertEqual(len(roles),1)
        answer=self.exchange(character_list_request())
        self.assertEqual(struct.unpack_from('<II',answer,20),(1,2))
        self.assertIn('テスト'.encode('utf-16le')+b'\0\0',answer)
        fields=roles[0]['native_fields']
        self.assertEqual(struct.unpack_from('<II',fields,0x18),roles[0]['identity'])
        self.assertEqual((struct.unpack_from('<I',fields,0x34)[0],struct.unpack_from('<I',fields,0x44)[0]),(2,5))
        self.assertEqual((fields[0x3c],fields[0x3d],fields[0x40]),(1,2,5))
        self.assertEqual(self.mutation_status(delete_character_request(roles[0]['identity'],11)),0)
        self.assertEqual(struct.unpack_from('<II',self.exchange(character_list_request()),20),(0,3))

    def test_character_persistence_after_server_restart(self):
        self.authorize()
        self.assertEqual(self.mutation_status(create_character_request('SavedHero',request_id=10)),0)
        identity=self.server.characters.list(1)[0]['identity']
        self.server.positions.save(1,identity,0x1110101,(19,7))
        self.sock.close();self.server.close()
        self.server=LocalAccountServer(self.temp.name,main_port=0,world_port=0,bind_extra=False)
        self.server.start()
        self.sock=socket.create_connection(('127.0.0.1',self.server.main_port));self.sock.settimeout(2)
        recv_frame(self.sock);self.authorize()
        self.assertEqual(self.server.characters.list(1)[0]['identity'],identity)
        self.assertEqual(self.server.positions.load(1,identity),{'map_id':0x1110101,'grid':(19,7),'restored':True})
        self.assertEqual(struct.unpack_from('<II',self.exchange(character_list_request()),20),(1,2))

    def test_world_positions_isolate_characters_and_survive_existing_store_migration(self):
        one=self.server.characters.create(1,create_character_request('PositionOne'))
        two=self.server.characters.create(1,create_character_request('PositionTwo'))
        self.server.positions.save(1,one,0x1110101,(19,7))
        self.assertEqual(self.server.positions.load(1,two)['grid'],(6,4))
        for account,identity,grid in [(2,one,(10,8)),(1,(one[0],2),(10,8)),(1,one,(31,7)),(1,one,(19,449))]:
            with self.assertRaises(ValueError):self.server.positions.save(account,identity,0x1110101,grid)
        self.assertEqual(self.server.positions.load(1,one)['grid'],(19,7))
        # A corrupted/obsolete saved cell must not strand the original client.
        with self.server.accounts.lock:
            self.server.accounts.db.execute('UPDATE world_positions SET grid_y=449 WHERE character_id=?',(one[0],))
            self.server.accounts.db.commit()
        self.assertEqual(self.server.positions.load(1,one)['grid'],(6,4))
        self.server.characters.delete(1,one)
        self.assertEqual(self.server.accounts.db.execute('SELECT COUNT(*) FROM world_positions WHERE character_id=?',(one[0],)).fetchone()[0],0)

    def test_three_slots_duplicates_and_request_replay(self):
        self.authorize()
        packet=create_character_request('One',request_id=10)
        self.assertEqual(self.mutation_status(packet),0)
        self.assertEqual(self.mutation_status(packet),0)
        self.assertEqual(len(self.server.characters.list(1)),1)
        self.assertEqual(self.mutation_status(create_character_request('One',request_id=11)),-1)
        for i,name in enumerate(('Two','Three'),12):
            self.assertEqual(self.mutation_status(create_character_request(name,request_id=i)),0)
        self.assertEqual(self.mutation_status(create_character_request('Four',request_id=14)),-1)
        self.assertEqual(struct.unpack_from('<II',self.exchange(character_list_request()),20),(3,0))

    def test_integrity_and_model_rejection_leave_database_unchanged(self):
        self.authorize()
        broken=bytearray(create_character_request('Broken',request_id=10));broken[-1]^=1
        self.assertEqual(self.mutation_status(bytes(broken)),-1)
        self.assertEqual(self.mutation_status(create_character_request('BadModel',(0,1,0,0,0,0,0,0,0,1),request_id=11)),-1)
        self.assertEqual(self.mutation_status(create_character_request('BadAppearance',(1,1,128,0,0,0,0,0,0,1),request_id=12)),-1)
        self.assertEqual(self.server.characters.list(1),[])

    def test_delete_cannot_touch_other_account(self):
        self.authorize()
        self.assertEqual(self.mutation_status(create_character_request('Owned',request_id=10)),0)
        identity=self.server.characters.list(1)[0]['identity']
        self.server.accounts.add('second','secondpass');self.authorize('second','secondpass')
        self.assertEqual(self.mutation_status(delete_character_request(identity,11)),-1)
        self.assertEqual(len(self.server.characters.list(1)),1)
        self.assertEqual(self.server.characters.list(2),[])

    def test_mutation_requires_game_login(self):
        self.sock.sendall(data405(create_character_request('Forbidden'),1,1,route=0xffef))
        with self.assertRaises(socket.timeout):self.sock.recv(1)
        self.assertEqual(self.server.characters.list(1),[])

    def test_world_admission_ack_and_same_connection_replay(self):
        identity=self.server.characters.create(1,create_character_request('WorldTest'))
        ticket=self.server.world_tickets.issue(1,identity)
        p=world_admission_request(11100,ticket,35)
        answer=self.exchange(p)
        self.assertEqual(struct.unpack_from('<HHI',answer,1),(0x19,9,35))
        self.assertEqual(self.exchange(p),answer)
        with socket.create_connection(('127.0.0.1',self.server.main_port)) as other:
            other.settimeout(.5);recv_frame(other)
            other.sendall(data405(p,1,1,route=0xffef))
            with self.assertRaises(socket.timeout):other.recv(1)

    def test_expired_or_deleted_character_world_ticket_is_rejected(self):
        identity=self.server.characters.create(1,create_character_request('ExpiredWorld'))
        expired=self.server.world_tickets.issue(1,identity,ttl=-1)
        self.sock.sendall(data405(world_admission_request(0,expired,35),1,1,route=0xffef))
        with self.assertRaises(socket.timeout):self.sock.recv(1)
        ticket=self.server.world_tickets.issue(1,identity)
        self.server.characters.delete(1,identity)
        self.sock.sendall(data405(world_admission_request(0,ticket,36),1,1,route=0xffef))
        with self.assertRaises(socket.timeout):self.sock.recv(1)

    def test_world_ticket_owner_and_unknown_ticket_rejected(self):
        identity=self.server.characters.create(1,create_character_request('OwnedWorld'))
        ticket=self.server.world_tickets.issue(1,identity)
        self.server.accounts.add('second','secondpass');self.authorize('second','secondpass')
        self.sock.sendall(data405(world_admission_request(0,ticket,35),1,1,route=0xffef))
        with self.assertRaises(socket.timeout):self.sock.recv(1)
        self.sock.sendall(data405(world_admission_request(0,0xffff,36),1,1,route=0xffef))
        with self.assertRaises(socket.timeout):self.sock.recv(1)


def verify_native_socket_roundtrip(binary):
    from emulate_account_transport import TransportFixture
    with tempfile.TemporaryDirectory() as out:
        server=LocalAccountServer(out,main_port=0,world_port=0,bind_extra=False)
        try:
            server.start();f=TransportFixture(binary);f.request()
            with socket.create_connection(('127.0.0.1',server.main_port)) as sock:
                sock.settimeout(2);greeting=recv_frame(sock)
                assert len(greeting)==84
                sock.sendall(f.frames[0]);reply=recv_frame(sock)
            f.dispatch(reply);f.invoke(0x61d9e0)
            result=f.read32(f.login+0x20)
            assert f.read32(f.login+0x18)==1 and f.read32(result+0x4c)!=0
            assert not f.assertions
            account={'native_login_status':1,'account_id':f.read32(result+0x48),
                     'login_sid':f.read32(result+0x4c),'native_assertions':0}
            from emulate_game_login import GameFixture
            g=GameFixture(binary);g.request_game()
            with socket.create_connection(('127.0.0.1',server.main_port)) as sock:
                sock.settimeout(2);recv_frame(sock)
                sock.sendall(g.frames[0]);game_reply=recv_frame(sock)
            g.dispatch(game_reply)
            assert bytes(g.uc.mem_read(g.info+0x14,1))==b'\x02'
            copied=bytes(g.uc.mem_read(g.read32(g.info+0x34),96))
            game=g.validate_result_slice(copied)
            assert game['branch']=='accepted' and not g.assertions
            from emulate_character_list import CharacterFixture
            c=CharacterFixture(binary);c.request_characters()
            with socket.create_connection(('127.0.0.1',server.main_port)) as sock:
                sock.settimeout(2);recv_frame(sock)
                # Each native fixture starts with a fresh request pool; authorize this socket first.
                sock.sendall(g.frames[0]);recv_frame(sock)
                sock.sendall(c.frames[0]);role_reply=recv_frame(sock)
            role=c.receive_list(parse405(role_reply)['payload'])
            assert role['branch']=='accepted' and not c.assertions
            return {'passed':True,'account':account,'game_prelogin':game,'character_list':role,
                    'level':'real_loopback_TCP_server_original_x86_protocol_handlers',
                    'fixture':'Three separate original-code fixtures; no continuous Windows event loop',
                    'substitutions':'See the account/game/character native evidence for each fixture boundary',
                    'does_not_prove':['Windows graphics','real startup transport mode','character/map gameplay']}
        finally:server.close()


def verify_native_character_roundtrip(binary):
    from emulate_character_mutation import MutationFixture
    from emulate_character_list import CharacterFixture
    from emulate_game_login import GameFixture
    with tempfile.TemporaryDirectory() as out:
        server=LocalAccountServer(out,main_port=0,world_port=0,bind_extra=False)
        server.start()
        def exchange_native(frame):
            g=GameFixture(binary);g.request_game()
            with socket.create_connection(('127.0.0.1',server.main_port)) as sock:
                sock.settimeout(2);recv_frame(sock)
                sock.sendall(g.frames[0]);recv_frame(sock)
                sock.sendall(frame);return parse405(recv_frame(sock))['payload']
        try:
            f=MutationFixture(binary);f.request_create('テスト',(2,1,0,0,0,0,0,0,0,1))
            created=f.receive_mutation(exchange_native(f.frames[0]),'create')
            identity=server.characters.list(1)[0]['identity']
            assert created['branch']=='accepted' and not f.assertions
            # Close and reopen the actual TCP service/database before native list parsing.
            server.close()
            server=LocalAccountServer(out,main_port=0,world_port=0,bind_extra=False);server.start()
            c=CharacterFixture(binary);c.request_characters()
            populated=c.receive_list(exchange_native(c.frames[0]),1)
            assert populated['branch']=='accepted' and populated['names']==['テスト']
            assert populated['available_slots']==2 and not c.assertions
            assert bytes.fromhex(populated['native_fields_hex'])==server.characters.list(1)[0]['native_fields']
            d=MutationFixture(binary);d.request_delete(identity)
            deleted=d.receive_mutation(exchange_native(d.frames[0]),'delete')
            assert deleted['branch']=='accepted' and not d.assertions and server.characters.list(1)==[]
            return {'passed':True,'created':created,'after_restart':populated,'deleted':deleted,
                    'level':'original_mutation_packets_real_TCP_persistent_SQLite_original_result_handlers',
                    'fixture':'Separate original-code fixtures, not a continuous graphical game session',
                    'does_not_prove':['actual character rendering','world login','map load','playability']}
        finally:server.close()


def verify_native_world_admission_roundtrip(binary):
    from emulate_world_admission import AdmissionFixture
    with tempfile.TemporaryDirectory() as out:
        server=LocalAccountServer(out,main_port=0,world_port=0,bind_extra=False)
        try:
            identity=server.characters.create(1,create_character_request('WorldNative'))
            ticket=server.world_tickets.issue(1,identity)
            server.start();f=AdmissionFixture(binary);f.request_admission(ticket)
            with socket.create_connection(('127.0.0.1',server.main_port)) as sock:
                sock.settimeout(2);recv_frame(sock);sock.sendall(f.frames[-1]);reply=recv_frame(sock)
            f.dispatch(reply);result=f.advance_after_reply()
            assert result['world_controller_stage']==7 and result['request_status']==2 and not f.assertions
            return {'passed':True,'result':result,'actual_reply_frame_hex':reply.hex(),
                    'level':'original_world_admission_request_real_TCP_local_ticket_validation_original_ACK_handler',
                    'fixture':'Ticket issued through research API, controller starts at stage 5; no automatic character selection handoff',
                    'does_not_prove':['continuous world login','later SID attachment','Windows client','map','playability']}
        finally:server.close()


if __name__=='__main__':unittest.main()


def verify_native_selection_admission_roundtrip(binary):
    from emulate_world_handoff import HandoffFixture
    with tempfile.TemporaryDirectory() as directory:
        server=LocalAccountServer(directory,world_route_probe=True,main_port=0,world_port=0,bind_extra=False)
        server.start()
        try:
            identity=server.characters.create(1,create_character_request('NativeRoute'))
            with socket.create_connection(('127.0.0.1',server.main_port)) as sock:
                sock.settimeout(1);recv_frame(sock)
                sock.sendall(data405(game_login_request('archive001','local123'),1,1,route=0xffef));recv_frame(sock)
                f=HandoffFixture(binary);f.write32(0x1040018,identity[0]);f.write32(0x104001c,identity[1])
                f.request_selection();sock.sendall(f.frames[-1]);reply=recv_frame(sock)
                selected=f.receive_selection(parse405(reply)['payload']);ticket=f.handoff()
                assert selected['branch']=='accepted' and ticket>0
                # Explicit socket-ready boundary; no native endpoint startup is claimed.
                f.write32(f.login+4,f.wrapper);f.write32(f.login+0x2c,5);f.write32(f.net+0xf4,11100)
                f.invoke(0x620760);sock.sendall(f.frames[-1]);ack=recv_frame(sock)
                f.dispatch(ack);f.invoke(0x620760)
                assert f.read32(f.login+0x2c)==7 and not f.assertions
                return {'passed':True,'character_identity':identity,'ticket':ticket,'selection_opcode':0x3c,
                        'ack_opcode':parse405(ack)['opcode'],'native_world_stage':7,'assertions':f.assertions,
                        'level':'actual TCP original selection request -> server ticket -> original parser/setter -> original admission request -> server ACK -> original stage 7',
                        'limitations':['experimental partial selection fields','stage 2..4 endpoint setup explicitly bypassed','game prelogin uses encoded request','no original Windows event loop, UDP, map or playability']}
        finally:server.close()


def verify_native_world_completion_roundtrip(binary):
    from emulate_world_completion import CompletionFixture
    with tempfile.TemporaryDirectory() as directory:
        server=LocalAccountServer(directory,main_port=0,world_port=0,bind_extra=False);server.start()
        try:
            identity=server.characters.create(1,create_character_request('CompleteNative'))
            ticket=server.world_tickets.issue(1,identity)
            with socket.create_connection(('127.0.0.1',server.main_port)) as control,socket.create_connection(('127.0.0.1',server.main_port)) as world:
                for sock in (control,world):sock.settimeout(1);recv_frame(sock)
                control.sendall(data405(login_request('archive001','local123'),1,1,route=0xffef));recv_frame(control)
                f=CompletionFixture(binary);f.write32(f.result+0x48,1)
                admission=f.request_admission(ticket);world.sendall(admission);admit_reply=recv_frame(world);f.accept_admission(admit_reply)
                attach=f.request_attachment();control.sendall(attach);reply=recv_frame(control)
                f.dispatch_channel(reply,f.world);wrong=f.advance()
                assert wrong['stage']==8 and wrong['result']==1
                f.dispatch_channel(reply,f.upstream);completed=f.advance()
                assert completed['stage']==9 and completed['result']==2 and not f.assertions
                return {'passed':True,'two_actual_TCP_connections':True,'admission_reply_opcode':parse405(admit_reply)['opcode'],
                        'control_reply_opcode':parse405(reply)['opcode'],'wrong_channel':wrong,'correct_channel':completed,
                        'level':'original two-channel requests -> live local ticket/account checks -> actual replies -> original stage 9/result 2',
                        'limitations':['Account login encoded request, ticket issued through research API','Socket startup stage 2..4 omitted','No Windows event loop, map or playability']}
        finally:server.close()
