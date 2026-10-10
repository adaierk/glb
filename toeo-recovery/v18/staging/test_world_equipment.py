"""Equipment ownership, location, packed bag, vitality, replay and restart invariants."""
import struct,tempfile,unittest
from pathlib import Path
from account_packets import message
from local_account_server import AccountStore,LocalAccountServer
from character_store import CharacterStore
from character_mutation_packets import create_character_request
from world_inventory_store import WorldInventoryStore,TradeRejected
from world_inventory_packets import parse_item_move_request
from world_profiles import RASHUAN
from native_data_packets import data405,parse405
class Capture:
    def __init__(self):self.answers=[]
    def sendall(self,value):self.answers.append(parse405(value)['payload'])

def equipment_packet(identity,item,source_location=2,source_slot=0,destination_location=4,destination_slot=1,sequence=1,other=(0,0,0,0)):
    p=bytearray(message(0x54,bytes(75),51))
    struct.pack_into('<IIII',p,12,sequence,RASHUAN.map_id,*identity)
    struct.pack_into('<IIII',p,28,*item)
    struct.pack_into('<IiiIi',p,44,source_location,source_slot,-1,destination_location,destination_slot)
    struct.pack_into('<IIII',p,64,*other)
    return bytes(p)

class EquipmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'accounts.sqlite'
        self.accounts=AccountStore(self.path);self.chars=CharacterStore(self.accounts)
        self.identity=self.chars.create(1,create_character_request('EquipHero'));self.store=WorldInventoryStore(self.accounts)
        self.initial=self.store.grant_equipment_preview(1,self.identity)
        self.sword,self.body=[x['identity'] for x in self.initial['items']]
    def tearDown(self):self.accounts.close();self.temp.cleanup()
    def move(self,p):return self.store.move(1,self.identity,parse_item_move_request(p),p,'equipment')
    def equip_both(self):
        self.move(equipment_packet(self.identity,self.sword))
        return self.move(equipment_packet(self.identity,self.body,destination_slot=2,sequence=2))[0]
    def test_equip_unequip_restart_and_bonus_clamp(self):
        both=self.equip_both();self.assertEqual(both['items'],[]);self.assertEqual([x['slot'] for x in both['equipment']],[1,2]);self.assertEqual(both['money'],5000)
        self.assertEqual(self.store.load_vitals(1,self.identity),{'hp':100,'tp':30,'max_hp':110,'max_tp':30})
        self.accounts.db.execute('UPDATE world_vitals SET hp=110');self.accounts.db.commit()
        p=equipment_packet(self.identity,self.body,4,2,2,-1,sequence=3)
        bare,_=self.move(p);self.assertEqual(bare['items'][0]['identity'],self.body);self.assertEqual(bare['items'][0]['slot'],0)
        self.assertEqual(self.store.load_vitals(1,self.identity)['hp'],100)
        self.accounts.close();self.accounts=AccountStore(self.path);self.store=WorldInventoryStore(self.accounts)
        self.assertEqual(self.store.load(1,self.identity),bare);self.assertEqual(len(self.store.grant_equipment_preview(1,self.identity)['equipment']),1)
        self.assertEqual(len(self.store.load(1,self.identity)['items']),1)
    def test_replay_after_another_move_returns_current_state(self):
        p=equipment_packet(self.identity,self.sword);self.move(p)
        current,_=self.move(equipment_packet(self.identity,self.sword,4,1,2,-1,sequence=2))
        replay,replayed=self.move(p);self.assertTrue(replayed);self.assertEqual(replay,current)
        conflict=equipment_packet(self.identity,self.body,destination_slot=2)
        with self.assertRaises(TradeRejected):self.move(conflict)
        self.assertEqual(self.store.load(1,self.identity),current)
    def test_reject_foreign_instance_slot_location_context_and_quantity(self):
        invalid=[equipment_packet(self.identity,self.sword,destination_slot=2),equipment_packet(self.identity,self.sword,source_slot=1),equipment_packet(self.identity,(0x71000099,1,1,0)),equipment_packet((2,1),self.sword)]
        p=bytearray(equipment_packet(self.identity,self.sword));struct.pack_into('<I',p,80,1);invalid.append(bytes(p))
        p=bytearray(equipment_packet(self.identity,self.sword));struct.pack_into('<i',p,52,2);invalid.append(bytes(p))
        for p in invalid:
            with self.assertRaises(TradeRejected):self.move(p)
            self.assertEqual(self.store.load(1,self.identity),self.initial)
    def test_non_equipment_and_full_bag_reject_without_losing_gear(self):
        self.equip_both()
        for i in range(32):self.accounts.db.execute('INSERT INTO world_inventory_items(character_id,account_id,source_key,catalog_index,name,buy_price,sell_price,quantity,slot) VALUES(?,?,?,0,?,0,0,1,?)',(*self.identity,'dummy-'+str(i),'dummy',i))
        self.accounts.db.commit();before=self.store.load(1,self.identity)
        with self.assertRaises(TradeRejected):self.move(equipment_packet(self.identity,self.sword,4,1,2,-1,sequence=3))
        with self.assertRaises(TradeRejected):self.move(equipment_packet(self.identity,before['items'][0]['identity'],destination_slot=3,sequence=3))
        self.assertEqual(self.store.load(1,self.identity),before)
    def test_native_unequip_to_empty_bag_cell_zero(self):
        self.equip_both()
        result,_=self.move(equipment_packet(self.identity,self.sword,4,1,2,0,sequence=3))
        self.assertEqual(result['items'][0]['slot'],0);self.assertEqual(result['items'][0]['identity'],self.sword)
        self.assertEqual([x['slot'] for x in result['equipment']],[2])

    def test_native_equipment_area_automatic_body_slot(self):
        p=bytearray(equipment_packet(self.identity,self.body,source_slot=1,destination_slot=1));struct.pack_into('<i',p,52,1)
        result,_=self.move(bytes(p));self.assertEqual(result['equipment'][0]['slot'],2)

    def test_native_single_item_quantity_one(self):
        p=bytearray(equipment_packet(self.identity,self.sword));struct.pack_into('<i',p,52,1)
        result,_=self.move(bytes(p));self.assertEqual(result['equipment'][0]['identity'],self.sword)

    def test_native_server_authenticated_wire_and_b2_bonus(self):
        server=LocalAccountServer(Path(self.temp.name)/'server',world_route_probe=True,account_database=self.path,world_profile='rashuan')
        try:
            p=equipment_packet(self.identity,self.body,source_slot=1,destination_slot=2)
            c=Capture();state={'world_account_control':{'account_id':1,'character_id':self.identity},'world_map_ready':True,'trade_connection_key':'wire'}
            server.process_game_bytes(c,11101,1,data405(p,1,1,route=0xffef),state)
            replies=c.answers
            self.assertEqual([struct.unpack_from('<H',x,1)[0] for x in replies],[0x67,0x6b,0x6c,0xb2]);self.assertEqual(struct.unpack_from('<h',replies[0],20)[0],0)
            self.assertEqual(server.inventory.load(1,self.identity)['equipment'][0]['slot'],2)
            c=Capture();server.process_game_bytes(c,11101,2,data405(p,1,1,route=0xffef),{})
            self.assertEqual(c.answers,[])
        finally:server.close()
