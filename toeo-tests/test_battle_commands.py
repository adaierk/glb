import struct,unittest
from account_packets import message
from world_battle_commands import battle_start_notice,parse_attack_request,validate_attack_request
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
if __name__=='__main__':unittest.main()
