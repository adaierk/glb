"""Execute original NPC chunks and shop extension; replace graphics boundaries."""
import argparse,json
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EIP
from emulate_map_initialization import MapFixture
from world_npc_packets import shop_actor_records,SHOP_IDENTITY,SHOP_GRID,SHOP_NAME
from world_map_packets import LOCAL_MAP_ID

class NpcFixture(MapFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.map_model,self.actor=0x10a0000,0x10a1000
        self.write32(self.game+0x7c,0x10a2000)
        self.write32(self.map_model+0x104,0x10a3000)
        self.projected=None;self.shop_extension=None
    def on_code(self,uc,va,size,x):
        sp=uc.reg_read(UC_X86_REG_ESP);obj=uc.reg_read(UC_X86_REG_ECX)
        if va==0x4db420:self.ret(self.map_model,4) # loaded map lookup
        elif va in (0x4db8f0,0x424700):
            uc.mem_write(obj,bytes(8 if va==0x4db8f0 else 12));self.ret(obj) # temporary container ctors
        elif va==0x509db0:
            state=self.read32(sp+4)
            self.projected={
                'identity':[self.read32(state),self.read32(state+4)],
                'category':self.read32(state+8),'controlled':uc.mem_read(state+0x14,1)[0],
                'map_id':self.read32(state+0x22c),
                'grid':[self.read32(state+0x230),self.read32(state+0x234)],
                'animation_action':self.read32(state+0x23c),
                'appearance_hex':bytes(uc.mem_read(state+0x38,24)).hex(),
                'hp':[self.read32(state+0x58),self.read32(state+0xf8)],
                'tp':[self.read32(state+0x5c),self.read32(state+0xfc)]}
            self.write32(self.actor+0x70,self.projected['category'])
            self.ret(self.actor,4) # renderer construction and map registration
        elif va==0x4fe670:self.ret(0,12) # actor graphical fade
        elif va==0x4fe510:
            p=self.read32(sp+4)
            self.shop_extension={'vtable':hex(self.read32(p)),'actor':self.read32(p+4),'kind':self.read32(p+8)}
            self.ret(0,4) # extension ownership boundary, allocation/tag remain native
        elif va==0x502ca0:self.ret(0,8) # graphical attachments
        elif va==0x4cbcf0:self.ret() # temp container destructor
        else:super().on_code(uc,va,size,x)

def run(binary):
    f=NpcFixture(binary);p=0x10a4000
    f.uc.mem_write(p,shop_actor_records())
    try:f.invoke(0x51c1e0,(LOCAL_MAP_ID,*SHOP_IDENTITY,p))
    except Exception as e:raise RuntimeError(f'{e}; native PC={hex(f.uc.reg_read(UC_X86_REG_EIP))}') from e
    assert f.projected['identity']==list(SHOP_IDENTITY)
    assert f.projected['category']==2 and f.projected['controlled']==0
    assert f.projected['map_id']==LOCAL_MAP_ID and f.projected['grid']==list(SHOP_GRID)
    assert f.projected['animation_action']==1
    assert f.decoded_names==[SHOP_NAME]
    assert f.shop_extension=={'vtable':'0x6eeca8','actor':f.actor,'kind':2}
    assert not f.assertions
    return dict(passed=True,native_projection=f.projected,native_names=f.decoded_names,
                native_shop_extension=f.shop_extension,
                limitations=['Graphics construction, loaded-map lookup, temporary containers, ownership and attachments explicitly substituted',
                             'Original chunks, name decoder, position fields, shop allocation and vtable execute unchanged',
                             'Does not establish Windows rendering or merchant interaction'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    Path(a.out).write_text(json.dumps(run(a.binary),indent=2));print('ORIGINAL_NPC_SHOP_CHUNK_PASS')
