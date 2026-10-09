"""Execute native movement rejection: stop path and restore accepted grid."""
import argparse
import json
from pathlib import Path
import struct
from unicorn.x86_const import UC_X86_REG_ESP
from emulate_movement_reply import MoveFixture
from world_movement_packets import move_rejection_reply
from native_map_geometry import grid_to_point


class RejectFixture(MoveFixture):
    def __init__(self,binary):
        super().__init__(binary);self.stopped=False;self.pose=None

    def on_code(self,uc,address,size,data):
        if address==0x424c70:
            self.stopped=True;self.ret()  # animation path container boundary
        elif address in (0x501200,0x501400):
            self.ret()  # animation/graphical model synchronization boundaries
        elif address==0x4ffa50:
            pointer=self.read32(uc.reg_read(UC_X86_REG_ESP)+4)
            self.pose=list(struct.unpack('<ff',uc.mem_read(pointer,8)));self.ret(0,4)
        else:super().on_code(uc,address,size,data)


def run(binary):
    f=RejectFixture(binary);f.write32(f.world+0x9c,5)
    move={'request_id':123,'sequence':5,'identity':(1,1),'map_id':0x1120108,
          'source':(131,321),'target':(129,323),'mode':1,'speed':1.0}
    reply=move_rejection_reply(move,(131,321));f.receive(reply,move['target'])
    position=list(struct.unpack('<ff',f.uc.mem_read(f.actor+0xc,8)))
    assert f.stopped and position==list(grid_to_point((131,321))) and f.pose==position
    assert not f.assertions
    return {'passed':True,'native_branch':'52B0CE','status':-93,'restored_grid':[131,321],
            'native_position':position,'path_stopped':f.stopped,
            'scope':'Original reply field reads, 4FF9C0 grid conversion and actor position assignment',
            'substitutions':['Inherited actor lookup/query boundaries','Animation path container stop',
                             'Animation/model synchronization and graphical pose setter'],
            'limitations':['Original status semantic name unknown; stop/restore behavior measured',
                           'Separate Windows run required for prediction rollback and persistence']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    result=run(a.binary);Path(a.out).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('ORIGINAL_MOVEMENT_REJECTION_STOP_RESTORE_PASS')
