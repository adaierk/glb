"""Run unchanged 529840 battle record parser to its renderer-registration boundary."""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP
from emulate_npc_creation import NpcFixture
from world_combat_packets import battle_actor_record,BATTLE_GROUP,BATTLE_ENEMY_BANK,BATTLE_ENEMY_RESOURCE_BANK
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
                'battle_model_bank':self.read32(p+0x24c),'category':self.read32(p+0x244),'map_id':self.read32(p+0x220),
                'group':[self.read32(p+0x228),self.read32(p+0x22c)],
                'position':[self.read32(p+0x230),self.read32(p+0x234)],
                'appearance_hex':bytes(uc.mem_read(p+0x34,24)).hex(),
                'hp':[self.read32(p+0x54),self.read32(p+0xf4)],
                'tp':[self.read32(p+0x58),self.read32(p+0xf8)]}
            uc.emu_stop()
        else:super().on_code(uc,va,size,context)
def record_projections(binary):
    rows=[]
    for identity,name,bank,category,position,controlled in [(ENEMY_IDENTITY,ENEMY_NAME,BATTLE_ENEMY_BANK,2,(96,0),False),((1,1),'ArchiveHero',0,1,(0,0),True)]:
        f=BattleRecordFixture(binary);appearance=bytearray(24)
        if bank:struct.pack_into('<I',appearance,8,bank)
        else:struct.pack_into('<II',appearance,0,1,1);struct.pack_into('<I',appearance,20,1)
        f.uc.mem_write(f.packet,battle_actor_record(identity,name,bytes(appearance),category,position,enemy_grid(RASHUAN),RASHUAN.map_id,tp=30,max_tp=30,controlled=controlled,battle_model_bank=0 if controlled else BATTLE_ENEMY_RESOURCE_BANK))
        try:f.invoke(0x529840,(f.packet,RASHUAN.map_id,f.group),this=0x10d8000)
        except RuntimeError as e:
            if f.projected is None or f.uc.reg_read(UC_X86_REG_EIP)!=0x515650:raise RuntimeError(f'{e}; PC={hex(f.uc.reg_read(UC_X86_REG_EIP))}') from e
            # invoke requires a return; this fixture intentionally stops at the declared renderer boundary.
        actual=f.projected
        assert actual and actual['identity']==list(identity) and actual['category']==category
        assert actual['map_id']==RASHUAN.map_id and actual['group']==list(BATTLE_GROUP)
        assert actual['position']==list(position) and actual['appearance_hex']==appearance.hex()
        assert actual['controlled']==int(controlled) and actual['hp']==[100,100] and actual['tp']==[30,30]
        assert actual['battle_model_bank']==(0 if controlled else BATTLE_ENEMY_RESOURCE_BANK)
        assert list(f.names.values())[-1]==name and not f.assertions
        rows.append(actual)
    return {'passed':True,'projections':rows,'substitutions':['Inherited OS/string/temp-container boundaries','515650 renderer-registration boundary; preceding original name/identity/vitals/appearance parser executed unchanged'],'does_not_prove':['Native Windows battle entry','Attack animations','Combat outcome']}

def run(binary):
    from emulate_npc_interaction import InteractionFixture
    from world_npc_packets import parse_npc_request
    from world_combat_packets import enemy_selection_reply
    from unicorn.x86_const import UC_X86_REG_ECX
    class EnemyInteraction(InteractionFixture):
        def on_code(self,uc,va,size,context):
            sp=uc.reg_read(UC_X86_REG_ESP)
            if va in (0x526340,0x49c840,0x508a80):
                identity=struct.unpack('<II',uc.mem_read(sp+4,8))
                self.ret(self.player if identity==(1,1) else self.npc if identity==ENEMY_IDENTITY else 0,16 if va==0x526340 else 8)
            else:super().on_code(uc,va,size,context)
    f=EnemyInteraction(binary);f.write32(f.player+0x14,RASHUAN.map_id)
    grid=0x10d9000;f.uc.mem_write(grid,struct.pack('<ii',*enemy_grid(RASHUAN)))
    f.invoke(0x522bd0,(*ENEMY_IDENTITY,grid,f.world_state+0xa0,0,0,1),this=0x10d8000)
    request=parse_npc_request(f.sent[-1]);assert request['target']==ENEMY_IDENTITY
    request['request_id']=123;f.write32(f.world_state+0xa8,1)
    f.receive(0x52cc40,enemy_selection_reply(request,RASHUAN))
    action=parse_npc_request(f.sent[-1])
    assert action['opcode']==0xc8 and action['action']==1 and action['target']==ENEMY_IDENTITY and not f.assertions
    result=record_projections(binary)
    result['original_encounter_action_request']=action
    result['native_encounter_menu_mask']=1
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    Path(a.out).write_text(json.dumps(run(a.binary),indent=2));print('ORIGINAL_BATTLE_59_RECORD_PROJECTION_PASS')
