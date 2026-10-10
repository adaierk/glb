"""Run unchanged 529840 battle record parser to its renderer-registration boundary."""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP
from emulate_npc_creation import NpcFixture
from world_combat_packets import battle_actor_record,BATTLE_GROUP,BATTLE_ENEMY_BANK
from world_enemy_packets import ENEMY_IDENTITY,ENEMY_NAME,enemy_grid
from world_profiles import RASHUAN
class BattleRecordFixture(NpcFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.group=0x10e0000;self.packet=0x10e1000
        self.uc.mem_write(self.group+8,struct.pack('<II',*BATTLE_GROUP))
        self.write32(self.group+0x20,0x10e2000)
        self.write32(self.game+0x28,0x10e3000)
        self.uc.mem_write(0x10e3000,struct.pack('<II',1,1))
        self.projected=None
    def on_code(self,uc,va,size,context):
        if va==0x515650:
            p=self.read32(uc.reg_read(UC_X86_REG_ESP)+4)
            self.projected={'identity':[self.read32(p),self.read32(p+4)],'controlled':uc.mem_read(p+0xc,1)[0],
                'category':self.read32(p+0x244),'map_id':self.read32(p+0x220),
                'group':[self.read32(p+0x228),self.read32(p+0x22c)],
                'position':[self.read32(p+0x230),self.read32(p+0x234)],
                'appearance_hex':bytes(uc.mem_read(p+0x34,24)).hex(),
                'hp':[self.read32(p+0x54),self.read32(p+0xf4)],
                'tp':[self.read32(p+0x58),self.read32(p+0x184)]}
            uc.emu_stop()
        else:super().on_code(uc,va,size,context)
def run(binary):
    rows=[]
    for identity,name,bank,category,position,controlled in [(ENEMY_IDENTITY,ENEMY_NAME,BATTLE_ENEMY_BANK,2,(96,0),False),((1,1),'ArchiveHero',0,1,(0,0),True)]:
        f=BattleRecordFixture(binary);appearance=bytearray(24)
        if bank:struct.pack_into('<I',appearance,8,bank)
        else:struct.pack_into('<II',appearance,0,1,1);struct.pack_into('<I',appearance,20,1)
        f.uc.mem_write(f.packet,battle_actor_record(identity,name,bytes(appearance),category,position,enemy_grid(RASHUAN),RASHUAN.map_id,tp=30,max_tp=30,controlled=controlled))
        try:f.invoke(0x529840,(f.packet,RASHUAN.map_id,f.group),this=0x10d8000)
        except Exception as e:raise RuntimeError(f'{e}; PC={hex(f.uc.reg_read(UC_X86_REG_EIP))}') from e
        actual=f.projected
        assert actual and actual['identity']==list(identity) and actual['category']==category
        assert actual['map_id']==RASHUAN.map_id and actual['group']==list(BATTLE_GROUP)
        assert actual['position']==list(position) and actual['appearance_hex']==appearance.hex()
        assert actual['controlled']==int(controlled) and actual['hp']==[100,100] and actual['tp']==[30,30]
        assert list(f.names.values())[-1]==name and not f.assertions
        rows.append(actual)
    return {'passed':True,'projections':rows,'substitutions':['Inherited OS/string/temp-container boundaries','515650 renderer-registration boundary; preceding original name/identity/vitals/appearance parser executed unchanged'],'does_not_prove':['Native Windows battle entry','Attack animations','Combat outcome']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    Path(a.out).write_text(json.dumps(run(a.binary),indent=2));print('ORIGINAL_BATTLE_59_RECORD_PROJECTION_PASS')
