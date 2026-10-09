"""Real persistence, command replay, rejected use rollback and wire checks."""
import struct,tempfile,unittest
from pathlib import Path
from local_account_server import AccountStore,LocalAccountServer
from character_store import CharacterStore
from character_mutation_packets import create_character_request
from world_inventory_store import WorldInventoryStore,TradeRejected
from world_inventory_packets import parse_trade_request,parse_shop_close_request
from world_npc_packets import SHOP_IDENTITY
from world_item_use_packets import parse_item_use_request
from world_shop_catalog import historical_stock,PREVIEW_SOURCE_KEY
from test_world_inventory import request as trade_packet
from account_packets import message
from world_profiles import RASHUAN
from native_data_packets import data405,parse405


def use_packet(identity,item,seq=2,slot=0,target=None,count=0):
    p=bytearray(message(0x55,bytes(67),41))
    struct.pack_into('<I',p,12,seq)
    struct.pack_into('<III',p,28,RASHUAN.map_id,*identity)
    struct.pack_into('<IIII',p,40,*item)
    struct.pack_into('<IiIII',p,56,2,slot,count,*(target or identity))
    return bytes(p)


class UseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'accounts.sqlite'
        self.accounts=AccountStore(self.path);self.characters=CharacterStore(self.accounts)
        self.identity=self.characters.create(1,create_character_request('UseHero'))
        self.store=WorldInventoryStore(self.accounts);self.source=historical_stock(PREVIEW_SOURCE_KEY)
        payload=trade_packet(0xde,1,self.identity,[(0,2)])
        self.before,_=self.store.trade(1,self.identity,self.source,parse_trade_request(payload),payload,'test')
        self.item=self.before['items'][0]['identity']
        with self.accounts.lock,self.accounts.db:
            self.accounts.db.execute('UPDATE world_vitals SET hp=40,tp=10 WHERE character_id=? AND account_id=?',self.identity)

    def tearDown(self):self.accounts.close();self.temp.cleanup()

    def use(self,payload):return self.store.use(1,self.identity,parse_item_use_request(payload),payload,'test')

    def test_recovery_once_restart_and_delete(self):
        p=use_packet(self.identity,self.item)
        snapshot,vitals,replayed=self.use(p)
        self.assertFalse(replayed);self.assertEqual(snapshot['items'][0]['quantity'],1)
        self.assertEqual(snapshot['money'],self.before['money']);self.assertEqual(vitals,{'hp':100,'tp':10,'max_hp':100,'max_tp':30})
        self.assertTrue(self.use(p)[2]);self.assertEqual(self.store.load(1,self.identity),snapshot)
        self.accounts.close();self.accounts=AccountStore(self.path);self.characters=CharacterStore(self.accounts);self.store=WorldInventoryStore(self.accounts)
        self.assertEqual(self.store.load_vitals(1,self.identity),vitals)
        self.assertEqual(self.store.load(1,self.identity),snapshot)
        self.characters.delete(1,self.identity)
        self.assertEqual(self.accounts.db.execute('SELECT COUNT(*) FROM world_vitals').fetchone()[0],0)

    def test_full_hp_foreign_target_slot_and_conflicting_replay_leave_state_intact(self):
        for p in (use_packet(self.identity,self.item,slot=99),use_packet(self.identity,self.item,target=(99,1)),
                  use_packet(self.identity,(0x710000ff,1,1,0))):
            with self.assertRaises(TradeRejected):self.use(p)
        self.assertEqual(self.store.load(1,self.identity),self.before)
        p=use_packet(self.identity,self.item);snapshot,vitals,_=self.use(p)
        with self.assertRaises(TradeRejected):self.use(use_packet(self.identity,self.item,seq=3))
        with self.assertRaises(TradeRejected):self.use(use_packet(self.identity,self.item,count=1))
        self.assertEqual(self.store.load(1,self.identity),snapshot);self.assertEqual(self.store.load_vitals(1,self.identity),vitals)

    def test_malformed_quantity_and_size(self):
        for p in (use_packet(self.identity,self.item,count=2),use_packet(self.identity,self.item)[:-4]):
            with self.assertRaises(ValueError):parse_item_use_request(p)

    def test_tp_recovery_last_stack_removal_and_old_replay_after_new_command(self):
        # Pine restores the historically recorded TP100, capped at local max30.
        payload=trade_packet(0xde,2,self.identity,[(2,1)])
        bought,_=self.store.trade(1,self.identity,self.source,parse_trade_request(payload),payload,'test')
        pine=bought['items'][1]['identity'];p=use_packet(self.identity,pine,seq=3,slot=1)
        snapshot,vitals,_=self.use(p)
        self.assertEqual(vitals['tp'],30);self.assertEqual(vitals['hp'],40)
        self.assertEqual(len(snapshot['items']),1)
        lemon=use_packet(self.identity,self.item,seq=4);latest,_,_=self.use(lemon)
        replay,_,flag=self.use(p)
        self.assertTrue(flag);self.assertEqual(replay,latest)

    def test_wire_reply_and_unauthorized_map(self):
        server=LocalAccountServer(self.temp.name,account_database=self.path,world_route_probe=True,world_profile='rashuan')
        class Capture:
            def __init__(self):self.answers=[]
            def sendall(self,value):self.answers.append(parse405(value)['payload'])
        c=Capture();state={'world_account_control':{'account_id':1,'character_id':self.identity},'world_map_ready':True,'trade_connection_key':'test'}
        p=use_packet(self.identity,self.item)
        try:
            server.process_game_bytes(c,11101,9,data405(p,1,1,route=0xffef),state)
            self.assertEqual([struct.unpack_from('<H',p,1)[0] for p in c.answers],[0x67,0x6b,0xb2])
            self.assertEqual(struct.unpack_from('<I',c.answers[0],5)[0],41)
            self.assertEqual(struct.unpack_from('<hh',c.answers[0],20),(0,0))
            c.answers=[];bad=dict(state,world_map_ready=False)
            server.process_game_bytes(c,11101,9,data405(p,1,1,route=0xffef),bad)
            self.assertEqual(c.answers,[])
        finally:server.close()

    def test_shop_close_receipt_preserves_save_and_allows_next_command(self):
        server=LocalAccountServer(self.temp.name,account_database=self.path,world_route_probe=True,shop_preview=True,world_profile='rashuan')
        class Capture:
            def __init__(self):self.answers=[]
            def sendall(self,value):self.answers.append(parse405(value)['payload'])
        c=Capture();state={'world_account_control':{'account_id':1,'character_id':self.identity},'world_map_ready':True,'shop_catalog_ack_observed':True,'trade_connection_key':'test'}
        close=bytearray(message(0xe0,bytes(27),41))
        struct.pack_into('<IIIIII',close,12,3,*self.identity,RASHUAN.map_id,*SHOP_IDENTITY)
        p=bytes(close);self.assertEqual(parse_shop_close_request(p)['sequence'],3)
        try:
            bad=bytearray(p);struct.pack_into('<I',bad,28,99)
            server.process_game_bytes(c,11101,9,data405(bad,1,1,route=0xffef),state)
            self.assertEqual(c.answers,[]);self.assertTrue(state['shop_catalog_ack_observed'])
            for _ in range(2):server.process_game_bytes(c,11101,9,data405(p,1,1,route=0xffef),state)
            self.assertEqual(len(c.answers),2)
            self.assertTrue(all(struct.unpack_from('<I',reply,5)[0]==41 and struct.unpack_from('<I',reply,12)[0]==3 for reply in c.answers))
            self.assertFalse(state['shop_catalog_ack_observed']);self.assertEqual(self.store.load(1,self.identity),self.before)
            c.answers=[];use=use_packet(self.identity,self.item,seq=4)
            server.process_game_bytes(c,11101,9,data405(use,1,1,route=0xffef),state)
            self.assertEqual([struct.unpack_from('<H',reply,1)[0] for reply in c.answers],[0x67,0x6b,0xb2])
            self.assertEqual(self.store.load(1,self.identity)['items'][0]['quantity'],1)
        finally:server.close()


if __name__=='__main__':unittest.main()
