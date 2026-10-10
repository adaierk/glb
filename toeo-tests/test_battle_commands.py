import struct,unittest
from account_packets import message
from world_battle_commands import battle_start_notice,parse_attack_request,validate_attack_request,action_record,actor_action_notice,parse_battle_move_request,attack_action_notice
class BattleCommandTests(unittest.TestCase):
    def packet(self,**changes):
        fields=dict(map_id=7,group=(9,1),identity=(1,1),command=10004,target=(2,1))
        fields.update(changes)
        return message(0xa8,bytes(3)+struct.pack('<11I',fields['map_id'],*fields['group'],*fields['identity'],fields['command'],*fields['target'],123,0,0),17)
    def test_cross_battle_and_target_authority(self):
        p=parse_attack_request(self.packet())
        validate_attack_request(p,(1,1),7,(9,1),(2,1))
        for changed in ({'identity':(3,1)},{'map_id':8},{'group':(0,0)},{'target':(1,1)},{'command':999}):
            with self.assertRaises(ValueError):validate_attack_request(parse_attack_request(self.packet(**changed)),(1,1),7,(9,1),(2,1))
        with self.assertRaises(ValueError):validate_attack_request(p,(1,1),7,(9,1),None)
    def test_malformed_native_packet(self):
        b=self.packet()
        for bad in (b[:-1],b+b'x',bytes([1])+b[1:],b[:1]+struct.pack('<H',0xa9)+b[3:]):
            with self.assertRaises(ValueError):parse_attack_request(bad)
    def test_start_is_group_scoped(self):
        b=battle_start_notice(7,(9,1),17)
        self.assertEqual(len(b),24)
        self.assertEqual(struct.unpack_from('<3I',b,12),(7,9,1))
        self.assertEqual(struct.unpack_from('<HHI',b,1),(0xaa,24,17))

    def test_movement_scope_and_coordinates(self):
        action=action_record((1,1),(320,0),2,1)
        b=bytearray(message(0xa7,bytes(31)+action,17))
        struct.pack_into('<4I',b,12,92,7,9,1)
        p=parse_battle_move_request(bytes(b),(1,1),7,(9,1))
        self.assertEqual(p['position'],(320,0))
        for identity,map_id,group in (((2,1),7,(9,1)),((1,1),8,(9,1)),((1,1),7,(0,0))):
            with self.assertRaises(ValueError):parse_battle_move_request(bytes(b),identity,map_id,group)
        for x,y in ((float('nan'),0),(float('inf'),0),(-1,0),(1601,0),(320,-1)):
            bad=bytearray(b);struct.pack_into('<ff',bad,52,x,y)
            with self.assertRaises(ValueError):parse_battle_move_request(bytes(bad),(1,1),7,(9,1))
        bad=bytearray(b);struct.pack_into('<I',bad,64,10004)
        with self.assertRaises(ValueError):parse_battle_move_request(bytes(bad),(1,1),7,(9,1))
    def test_native_action_carrier(self):
        a=parse_attack_request(self.packet())
        b=attack_action_notice(a,(320,0))
        self.assertEqual(len(b),96)
        self.assertEqual(struct.unpack_from('<ff',b,52),(532,0))
        self.assertEqual(struct.unpack_from('<6I',b,12),(96,7,9,1,1,1))
        self.assertEqual(struct.unpack_from('<HH',b,40),(0x5a,13))
        self.assertEqual(struct.unpack_from('<I',b,64)[0],10004)
        self.assertEqual(struct.unpack_from('<II',b,76),(2,1))
        self.assertEqual(b[-4:],bytes(4))
        with self.assertRaises(ValueError):actor_action_notice(7,(9,1),(2,1),b[40:92])
if __name__=='__main__':unittest.main()
