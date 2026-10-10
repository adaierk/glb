"""Execute unchanged original 22/2E enemy parser with explicit boundaries."""
import argparse,json
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EIP
from emulate_npc_creation import NpcFixture
from world_enemy_packets import enemy_actor_records,enemy_grid,ENEMY_IDENTITY,ENEMY_NAME,ENEMY_MODEL_BANK
from world_profiles import RASHUAN
class EnemyFixture(NpcFixture):
    def __init__(self,binary):
        super().__init__(binary);self.native_mode=None;self.enemy_fields=None
    def on_code(self,uc,va,size,context):
        sp=uc.reg_read(UC_X86_REG_ESP)
        if va==0x506a00:self.ret(0,4)
        elif va==0x506d30:
            p=self.read32(sp+8)
            self.native_mode={'index':self.read32(sp+4),'vtable':hex(self.read32(p))}
            self.ret(0,8)
        elif va==0x4fe510:
            p=self.read32(sp+4)
            self.enemy_fields={'level':self.read32(p+0xc),'battle_group':self.read32(p+0x14),'style':self.read32(p+0x2c)}
            super().on_code(uc,va,size,context)
        else:super().on_code(uc,va,size,context)
def run(binary):
    f=EnemyFixture(binary);packet=0x10a4000
    f.uc.mem_write(packet,enemy_actor_records(RASHUAN))
    try:f.invoke(0x51c1e0,(RASHUAN.map_id,*ENEMY_IDENTITY,packet))
    except Exception as e:raise RuntimeError(f'{e}; PC={hex(f.uc.reg_read(UC_X86_REG_EIP))}') from e
    assert f.projected['identity']==list(ENEMY_IDENTITY) and f.projected['category']==2
    assert f.projected['grid']==list(enemy_grid(RASHUAN))
    assert f.projected['animation_action']==1 and f.projected['hp']==[100,100]
    assert bytes.fromhex(f.projected['appearance_hex'])[8:12]==ENEMY_MODEL_BANK.to_bytes(4,'little')
    assert f.shop_extension=={'vtable':'0x6eebe4','actor':f.actor,'kind':1}
    assert f.native_mode=={'index':2,'vtable':'0x6eecb8'}
    assert f.enemy_fields=={'level':0xffffffff,'battle_group':0,'style':2}
    assert f.decoded_names==[ENEMY_NAME] and not f.assertions
    return {'passed':True,'native_projection':f.projected,'native_enemy_extension':f.shop_extension,
            'native_mode':f.native_mode,'native_fields':f.enemy_fields,
            'provenance':'Explicit local E000 test encounter; official spawn/stat configuration unresolved',
            'substitutions':['Inherited map/resource/string/OS/renderer construction boundaries',
                             'Native mode and extension ownership boundaries; allocation and field parsing run unchanged'],
            'windows_rendering_proven':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    Path(a.out).write_text(json.dumps(run(a.binary),indent=2));print('ORIGINAL_ENEMY_22_2E_COMPONENT_PASS')
