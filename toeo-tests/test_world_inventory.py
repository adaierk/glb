"""Transaction rollback, ownership, replay, restart and deletion checks."""
import struct,tempfile,unittest
from pathlib import Path
from local_account_server import AccountStore,LocalAccountServer
from character_store import CharacterStore
from character_mutation_packets import create_character_request
from world_inventory_store import WorldInventoryStore,TradeRejected
from world_inventory_packets import parse_trade_request
from world_shop_catalog import historical_stock,PREVIEW_SOURCE_KEY
from world_npc_packets import SHOP_IDENTITY
from world_profiles import RASHUAN
from account_packets import message
from native_data_packets import data405,parse405


def request(op,sequence,identity,lines):
    stride=8 if op==0xde else 24
    packet=bytearray(message(op,bytes(31+len(lines)*stride),31))
    struct.pack_into('<IIIIIII',packet,12,sequence,*identity,RASHUAN.map_id,*SHOP_IDENTITY,len(lines))
    for n,line in enumerate(lines):struct.pack_into('<'+'I'*(stride//4),packet,40+stride*n,*line)
    return bytes(packet)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'accounts.sqlite'
        self.accounts=AccountStore(self.path);self.characters=CharacterStore(self.accounts)
        self.identity=self.characters.create(1,create_character_request('TradeHero'))
        self.store=WorldInventoryStore(self.accounts);self.source=historical_stock(PREVIEW_SOURCE_KEY)

    def tearDown(self):self.accounts.close();self.temp.cleanup()

    def trade(self,op,seq,lines,connection='test'):
        payload=request(op,seq,self.identity,lines)
        return self.store.trade(1,self.identity,self.source,parse_trade_request(payload),payload,connection)

    def test_buy_sell_restart_and_delete(self):
        self.assertEqual(self.store.load(1,self.identity)['money'],5000)
        bought,_=self.trade(0xde,1,[(0,3)])
        self.assertEqual((bought['money'],bought['items'][0]['quantity']),(3920,3))
        sold,_=self.trade(0xdf,2,[(*bought['items'][0]['identity'],2,1)])
        self.assertEqual((sold['money'],sold['items'][0]['quantity']),(4100,2))
        self.accounts.close();self.accounts=AccountStore(self.path);self.characters=CharacterStore(self.accounts)
        self.store=WorldInventoryStore(self.accounts)
        self.assertEqual(self.store.load(1,self.identity),sold)
        # Native sequence starts anew for a new connection, without collision.
        again,_=self.trade(0xde,1,[(0,1)],connection='new-login')
        self.assertEqual((again['money'],again['items'][0]['quantity']),(3740,3))
        self.characters.delete(1,self.identity)
        for table in ('world_wallets','world_inventory_items','world_trade_ledger'):
            self.assertEqual(self.accounts.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)

    def test_batch_failure_rolls_back_and_replay_is_idempotent(self):
        initial=self.store.load(1,self.identity)
        with self.assertRaises(TradeRejected):self.trade(0xde,1,[(0,1),(2,4)])
        self.assertEqual(self.store.load(1,self.identity),initial)
        bought,replayed=self.trade(0xde,2,[(0,3)])
        self.assertFalse(replayed)
        receipt,replayed=self.trade(0xde,2,[(0,3)])
        self.assertTrue(replayed);self.assertEqual(receipt['money'],3920)
        self.assertEqual(self.store.load(1,self.identity),bought)
        with self.assertRaises(TradeRejected):self.trade(0xde,2,[(0,4)])
        self.assertEqual(self.store.load(1,self.identity),bought)

    def test_limits_instances_and_ownership(self):
        initial=self.store.load(1,self.identity)
        for lines in ([(0,1),(0,1)],[(99,1)]):
            with self.assertRaises(TradeRejected):self.trade(0xde,1,lines)
        with self.assertRaises(ValueError):parse_trade_request(request(0xde,1,self.identity,[(0,0)]))
        bought,_=self.trade(0xde,2,[(0,3)])
        for line in ((*bought['items'][0]['identity'],2,4),(0x710000ff,1,1,0,2,1)):
            with self.assertRaises(TradeRejected):self.trade(0xdf,3,[line])
        with self.assertRaises(TradeRejected):self.store.load(2,self.identity)
        with self.assertRaises(TradeRejected):self.store.load(1,(999999,1))
        self.assertEqual(self.store.load(1,self.identity),bought)

    def test_server_wire_trade_and_unauthorized_state(self):
        server=LocalAccountServer(self.temp.name,account_database=self.path,world_route_probe=True,shop_preview=True,world_profile='rashuan')
        class Capture:
            def __init__(self):self.answers=[]
            def sendall(self,value):self.answers.append(parse405(value)['payload'])
        c=Capture();state={'game_account_id':1,'world_account_control':{'account_id':1,'character_id':self.identity},
            'world_map_ready':True,'npc_selected':SHOP_IDENTITY,'shop_catalog_ack_observed':True}
        payload=request(0xde,1,self.identity,[(0,3)])
        try:
            server.process_game_bytes(c,11101,9,data405(payload,1,1,route=0xffef),state)
            self.assertEqual([struct.unpack_from('<H',p,1)[0] for p in c.answers],[0x67,0x6b])
            self.assertEqual(struct.unpack_from('<IIhh',c.answers[0],12),(1,52,0,0))
            self.assertEqual(struct.unpack_from('<I',c.answers[0],5)[0],31)
            self.assertEqual(struct.unpack_from('<H',c.answers[1],32)[0],0x36)
            self.assertEqual(server.inventory.load(1,self.identity)['money'],3920)
            server.process_game_bytes(c,11101,9,data405(payload,1,1,route=0xffef),state)
            self.assertEqual(server.inventory.load(1,self.identity)['money'],3920)
            bad=dict(state);bad.pop('world_map_ready');c.answers=[]
            server.process_game_bytes(c,11101,9,data405(request(0xde,2,self.identity,[(0,1)]),1,1,route=0xffef),bad)
            self.assertEqual(c.answers,[])
        finally:server.close()


if __name__=='__main__':unittest.main()
