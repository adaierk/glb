"""Original success reply branch, grid comparison and speed updates.

Actor lookup, alternate path application and query disposal are boundaries;
the original reply field reads, sequence check and grid comparison execute.
"""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EBX,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_ESP
from emulate_character_list import CharacterFixture
from native_map_geometry import grid_to_point
from world_movement_packets import move_reply

class MoveFixture(CharacterFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.actor,self.path,self.meta,self.world,self.actors=0x10b0000,0x10b0800,0x10b1000,0x10b1400,0x10b1800
        self.packet=0x10b2000;self.released=False;self.applied=None;self.stale_ack=False
        self.write32(self.game+0x74,self.world);self.write32(self.game+0x78,self.actors)
        self.write32(self.actor+0x12c,self.path);self.write32(self.path+0x60,self.meta)
        for off,value in ((0xac,64),(0xb0,32),(0xcc,32),(0xd0,16)):self.write32(self.meta+off,value)
        self.uc.mem_write(self.meta+0xc8,struct.pack('<f',.5))

    def on_code(self,uc,address,size,data):
        sp=uc.reg_read(UC_X86_REG_ESP)
        if address==0x508a80:
            ids=struct.unpack('<II',uc.mem_read(sp+4,8))
            self.ret(self.actor if ids==(1,1) else 0,8)
        elif address==0x50b730:
            args=struct.unpack('<9I',uc.mem_read(sp+4,36))
            self.applied={'actor':args[0],
                'target':struct.unpack('<ii',uc.mem_read(args[1],8)),
                'source':struct.unpack('<ii',uc.mem_read(args[2],8)),
                'mode':args[3],'speed':struct.unpack('<f',struct.pack('<I',args[4]))[0]}
            self.ret()
        elif address==0x4cac70:self.released=True;self.ret()
        elif address==0x52fee4:uc.emu_stop()
        else:super().on_code(uc,address,size,data)

    def receive(self,reply,target):
        self.uc.mem_write(self.packet,reply);self.write32(self.path+0x14,1)
        self.uc.mem_write(self.path+0x54,struct.pack('<ff',*grid_to_point(target)))
        self.uc.reg_write(UC_X86_REG_EBX,self.packet);self.uc.reg_write(UC_X86_REG_EDI,0)
        self.uc.reg_write(UC_X86_REG_EBP,0x20fd000);self.uc.reg_write(UC_X86_REG_ESP,0x20fc000)
        self.uc.emu_start(0x52ae8a,0x52fee4,count=2000)
        return {'query_released':self.released,'alternate_path':self.applied,
            'path_speed':struct.unpack('<f',self.uc.mem_read(self.path+0x28,4))[0],
            'actor_speed':struct.unpack('<f',self.uc.mem_read(self.actor+0x140,4))[0]}

def run(binary):
    move={'request_id':123,'sequence':1,'identity':(1,1),'map_id':0x1110101,
        'source':(6,4),'target':(10,8),'mode':2,'speed':1.5}
    cases={}
    for label,target in [('same',(10,8)),('different',(8,6))]:
        f=MoveFixture(binary);f.write32(f.world+0x9c,1)
        result=f.receive(move_reply(move),target);cases[label]=result
        assert result['query_released'],result
        if label=='same':assert result['alternate_path'] is None and result['path_speed']==result['actor_speed']==1.5,result
        else:assert result['alternate_path']=={'actor':f.actor,'target':(10,8),'source':(6,4),'mode':2,'speed':1.5},result
    return {'passed':True,'cases':cases,'scope':'original 52AE8A success reply branch, 423830/413BD0 grid comparison and 423820 speed setter',
        'substitutions':['actor collection lookup 508A80','alternate path application 50B730','query disposal 4CAC70'],
        'does_not_prove':['complete receive transport','real map collision or movement']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    result=run(a.binary);Path(a.out).write_text(json.dumps(result,indent=2))
    print('ORIGINAL_MOVEMENT_REPLY_BRANCH_PASS')
