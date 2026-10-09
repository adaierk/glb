"""Execute the original map-ready permission setter and input permission branch."""
import argparse,json
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_ESP
from emulate_character_list import CharacterFixture
from world_map_packets import world_map_ready_reply

class PermissionFixture(CharacterFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.actor,self.packet=0x10b0000,0x10b0800
        self.boundary=None

    def on_code(self,uc,address,size,data):
        if address in (0x52a3b8,0x505bbe,0x505bcb):
            self.boundary=address;uc.emu_stop()
        else:super().on_code(uc,address,size,data)

    def check(self,packet):
        self.uc.mem_write(self.packet,bytes(packet))
        self.uc.mem_write(self.actor+0x144,b'\0')
        self.uc.reg_write(UC_X86_REG_EBX,self.packet)
        self.uc.reg_write(UC_X86_REG_ESI,self.actor)
        self.uc.reg_write(UC_X86_REG_ESP,0x20fe000)
        self.uc.emu_start(0x52a3a8,0x52a3b8,count=50)
        permitted=bytes(self.uc.mem_read(self.actor+0x144,1))[0]
        self.uc.reg_write(UC_X86_REG_EDI,self.actor)
        self.uc.reg_write(UC_X86_REG_EBP,0x20fd000)
        self.write32(0x20fd000-0x40,0)
        self.boundary=None
        self.uc.emu_start(0x505bad,0x505bd2,count=50)
        return {'permission':permitted,'input_branch':hex(self.boundary)}

def run(binary):
    f=PermissionFixture(binary)
    reply=world_map_ready_reply(1)
    enabled=f.check(reply)
    old=bytearray(reply);old[18]=0
    disabled=f.check(old)
    assert enabled=={'permission':1,'input_branch':'0x505bcb'},enabled
    assert disabled=={'permission':0,'input_branch':'0x505bbe'},disabled
    return {'passed':True,'enabled':enabled,'disabled':disabled,
        'scope':'original 52A3A8 -> 4FE6C0 setter and 505BAD movement permission branch',
        'does_not_prove':['complete mouse input loop','successful path search','map movement']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    result=run(a.binary);Path(a.out).write_text(json.dumps(result,indent=2))
    print('ORIGINAL_MOVEMENT_PERMISSION_BRANCH_PASS')
