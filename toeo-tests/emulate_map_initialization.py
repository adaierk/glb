"""Original map record parsing with declared constructors, strings and OS boundaries."""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX,UC_X86_REG_EIP
from emulate_character_list import CharacterFixture
from world_map_packets import world_initialization_reply
from character_store import native_character_fields
from emulate_session_bootstrap import EXPECTED_SHA256

class MapFixture(CharacterFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.world_state,self.data,self.clock=0x1090000,0x1091000,0x1095000
        self.write32(self.game+0x74,self.world_state);self.write32(self.world_state+0x10,self.data)
        self.write32(self.world_state+0x14,0x1096000);self.write32(self.game+0xc4,self.clock)
        self.strings={};self.notices=[]
        for i,iat in enumerate((0x6e23dc,0x6e234c,0x6e2338,0x6e27fc,0x6e2110,0x6e210c)):
            self.write32(iat,0x1098000+i*16)
    def on_code(self,uc,va,size,x):
        sp=uc.reg_read(UC_X86_REG_ESP);obj=uc.reg_read(UC_X86_REG_ECX)
        if va==0x1098000: # narrow basic_string assignment
            source=self.read32(sp+4);raw=bytes(uc.mem_read(source,32)).split(b'\0')[0]
            self.strings[obj]=raw.decode('ascii');self.ret(obj,4)
        elif va==0x1098010: self.ret(obj,4) # basic_string copy; packet reads remain native
        elif va==0x1098020:self.ret(0x1099000) # basic_string c_str at UI name boundary
        elif va==0x1098030:self.ret(1000) # GetTickCount
        elif va in (0x1098040,0x1098050):self.ret(1,4 if va==0x1098040 else 8) # OS calendar/time conversion
        elif va==0x4ff5f0:
            uc.mem_write(obj,bytes(0x39c));self.ret(obj) # default state construction, not record parsing
        elif va in (0x43e070,):self.ret() # temporary state destructor
        elif va in (0x51fbb0,):self.ret(0,8) # non-rendered auxiliary component setter
        elif va==0x4cb3e0:self.ret(0,4) # UI character-name update
        elif va==0x613b40:
            source=self.read32(sp+12);n=struct.unpack('<H',uc.mem_read(source+3,2))[0]
            self.notices.append(bytes(uc.mem_read(source,n)).hex());self.ret(1,12) # native built notification send boundary
        else:super().on_code(uc,va,size,x)

def run(binary):
    f=MapFixture(binary);p=0x109a000
    fields=native_character_fields((1,1),'Archive',(1,1,0,0,0,0,0,0,0,0))
    reply=world_initialization_reply((1,1),'Archive',fields,1)
    f.uc.mem_write(p,reply)
    try:f.invoke(0x43f090,(p,p+40),this=f.ui)
    except Exception as e:
        raise RuntimeError(f'{e}; native PC={hex(f.uc.reg_read(UC_X86_REG_EIP))}') from e
    result=f.uc.reg_read(UC_X86_REG_EAX)
    assert result==0 and not f.assertions
    assert f.read32(f.data+0x14)==1110101
    assert [f.read32(f.data+0xe0),f.read32(f.data+0xe4)]==[1,1]
    assert list(f.strings.values())==['map/1110101.mpd','map/1110101.mpi','map/1110101.bnd','']
    return dict(passed=True,original_sha256=EXPECTED_SHA256,native_result=result,
                native_map_id=f.read32(f.data+0x14),paths=f.strings,
                native_entity_id=[f.read32(f.data+0xe0),f.read32(f.data+0xe4)],
                native_notifications=f.notices,reply_bytes=len(reply),
                limitations=['State/constructor/standard-library/OS/UI and send boundaries explicitly substituted',
                             'Original record tags, copying, traversal and parse result executed',
                             'Does not prove real map resources load or GUI/playability'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    Path(a.out).write_text(json.dumps(run(a.binary),indent=2));print('ORIGINAL_MAP_INITIALIZATION_RECORD_PARSE_PASS')
