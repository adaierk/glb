"""Reject stale and cross-character acknowledgements before initializing actors."""
import struct,unittest
from account_packets import message
from world_combat_packets import BATTLE_GROUP
from world_battle_initialization import battle_control_notice,battle_abilities_notice,validate_initialization_ack
class BattleInitializationTests(unittest.TestCase):
    def ack(self,op=0xa2,request_id=42,identity=(1,1),map_id=0x1120108,group=BATTLE_GROUP):
        return message(op,bytes(3)+struct.pack('<5I',*identity,map_id,*group),request_id)
    def test_control_and_empty_abilities_native_layout(self):
        c=battle_control_notice((1,1),0x1120108,42)
        a=battle_abilities_notice((1,1),0x1120108,43)
        self.assertEqual(len(c),36);self.assertEqual(len(a),44)
        self.assertEqual(struct.unpack_from('<6I',c,12),(1,1,0x1120108,*BATTLE_GROUP,0))
        self.assertEqual(struct.unpack_from('<3I',a,32),(0,0,0))
    def test_stale_or_cross_session_ack_rejected(self):
        self.assertTrue(validate_initialization_ack(self.ack(),0xa2,42,(1,1),0x1120108))
        for p in (self.ack(request_id=41),self.ack(identity=(2,1)),self.ack(map_id=1),self.ack(group=(1,1)),self.ack(op=0xa4),self.ack()+bytes(1),self.ack()[:-1]):
            with self.assertRaises(ValueError):validate_initialization_ack(p,0xa2,42,(1,1),0x1120108)
    def test_ability_rows_bounded(self):
        a=battle_abilities_notice((1,1),0x1120108,43,1,0,[(1,0,1,1)])
        self.assertEqual(len(a),60);self.assertEqual(struct.unpack_from('<I',a,40)[0],1)
        with self.assertRaises(ValueError):battle_abilities_notice((1,1),1,1,abilities=[(1,0,1,129)])
        with self.assertRaises(ValueError):battle_abilities_notice((1,1),1,1,attack_count=-1)
if __name__=='__main__':unittest.main()
