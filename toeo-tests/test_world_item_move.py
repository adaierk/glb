"""Packed bag order persistence, atomic swaps, migration and rejected native moves."""
import struct,unittest,tempfile
from pathlib import Path
from account_packets import message
from local_account_server import AccountStore,LocalAccountServer
from character_store import CharacterStore
from character_mutation_packets import create_character_request
from world_inventory_store import WorldInventoryStore,TradeRejected
from world_inventory_packets import parse_item_move_request,parse_trade_request
from world_shop_catalog import historical_stock,PREVIEW_SOURCE_KEY
from world_profiles import RASHUAN
from test_world_inventory import request as trade_packet
from test_world_item_use import use_packet
from world_item_use_packets import parse_item_use_request
from native_data_packets import data405,parse405

def move_packet(identity,item,source=0,destination=1,other=(0,0,0,0),sequence=2):
    p=bytearray(message(0x54,bytes(75),51))
    struct.pack_into('<IIII',p,12,sequence,RASHUAN.map_id,*identity)
    struct.pack_into('<IIII',p,28,*item)
    struct.pack_into('<IiiIi',p,44,2,source,-1,2,destination)
    struct.pack_into('<IIII',p,64,*other)
    return bytes(p)

class MoveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'accounts.sqlite'
        self.accounts=AccountStore(self.path);self.chars=CharacterStore(self.accounts)
        self.identity=self.chars.create(1,create_character_request('MoveHero'))
        self.store=WorldInventoryStore(self.accounts);self.stock=historical_stock(PREVIEW_SOURCE_KEY)
        p=trade_packet(0xde,1,self.identity,[(0,2),(1,1)])
        self.before,_=self.store.trade(1,self.identity,self.stock,parse_trade_request(p),p,'move')
        self.first,self.second=[x['identity'] for x in self.before['items']]
    def tearDown(self):self.accounts.close();self.temp.cleanup()
    def move(self,p):return self.store.move(1,self.identity,parse_item_move_request(p),p,'move')
    def test_end_move_restart_use_and_append(self):
        p=move_packet(self.identity,self.first,destination=-1);moved,replay=self.move(p)
        self.assertFalse(replay);self.assertEqual({x['identity']:x['slot'] for x in moved['items']},{self.first:1,self.second:0})
        self.assertEqual(moved['money'],self.before['money']);self.assertTrue(self.move(p)[1])
        self.accounts.close();self.accounts=AccountStore(self.path);self.store=WorldInventoryStore(self.accounts)
        self.assertEqual(self.store.load(1,self.identity),moved)
        with self.accounts.lock,self.accounts.db:self.accounts.db.execute('UPDATE world_vitals SET hp=40 WHERE character_id=? AND account_id=?',self.identity)
        use=use_packet(self.identity,self.first,seq=3,slot=1)
        used,_,_=self.store.use(1,self.identity,parse_item_use_request(use),use,'move')
        self.assertEqual(next(x for x in used['items'] if x['identity']==self.first)['quantity'],1)
        buy=trade_packet(0xde,4,self.identity,[(2,1)])
        bought,_=self.store.trade(1,self.identity,self.stock,parse_trade_request(buy),buy,'move')
        self.assertEqual(next(x for x in bought['items'] if x['name']=='パイングミ')['slot'],2)
        replay,flag=self.move(p);self.assertTrue(flag);self.assertEqual(replay,bought)
    def test_atomic_swap_and_rejections(self):
        p=move_packet(self.identity,self.first,other=self.second);moved,_=self.move(p)
        self.assertEqual({x['identity']:x['slot'] for x in moved['items']},{self.first:1,self.second:0})
        for p in (move_packet(self.identity,self.first,source=0,destination=-1,sequence=3),move_packet(self.identity,self.first,source=1,destination=0,sequence=3),move_packet(self.identity,self.first,source=1,destination=32,sequence=3),move_packet(self.identity,(99,1,1,0),source=1,destination=-1,sequence=3)):
            with self.assertRaises(TradeRejected):self.move(p)
        self.assertEqual(self.store.load(1,self.identity),moved)
        self.assertEqual(self.accounts.db.execute('SELECT COUNT(*) FROM world_inventory_items WHERE slot=-1').fetchone()[0],0)
        with self.assertRaises(TradeRejected):self.move(move_packet(self.identity,self.first,source=1,destination=8))
        p=bytearray(move_packet(self.identity,self.first,source=1,destination=8,sequence=3));struct.pack_into('<I',p,56,1)
        with self.assertRaises(TradeRejected):self.move(bytes(p))
        for value in (b'',bytes(p)[:-4]):
            with self.assertRaises(ValueError):parse_item_move_request(value)
    def test_sparse_wire_receipt_and_authenticated_map(self):
        server=LocalAccountServer(self.temp.name,account_database=self.path,world_route_probe=True,world_profile='rashuan')
        class Capture:
            def __init__(self):self.answers=[]
            def sendall(self,p):self.answers.append(parse405(p)['payload'])
        c=Capture();state={'world_account_control':{'account_id':1,'character_id':self.identity},'world_map_ready':True,'trade_connection_key':'move'}
        p=move_packet(self.identity,self.first,destination=-1)
        try:
            server.process_game_bytes(c,11101,9,data405(p,1,1,route=0xffef),state)
            self.assertEqual([struct.unpack_from('<H',x,1)[0] for x in c.answers],[0x67,0x6b])
            self.assertEqual(struct.unpack_from('<I',c.answers[0],5)[0],51)
            self.assertEqual(struct.unpack_from('<h',c.answers[0],20)[0],0)
            c.answers=[];server.process_game_bytes(c,11101,9,data405(p,1,1,route=0xffef),dict(state,world_map_ready=False));self.assertEqual(c.answers,[])
        finally:server.close()
    def test_legacy_slot_migration_preserves_instances(self):
        self.accounts.db.execute('DROP INDEX world_inventory_unique_location_slot')
        self.accounts.db.execute('ALTER TABLE world_inventory_items DROP COLUMN slot');self.accounts.db.commit()
        self.accounts.close();self.accounts=AccountStore(self.path);self.store=WorldInventoryStore(self.accounts)
        self.assertEqual(self.store.load(1,self.identity),self.before)
        WorldInventoryStore(self.accounts);self.assertEqual(self.store.load(1,self.identity),self.before)
