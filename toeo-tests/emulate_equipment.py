"""Execute unchanged equipment 54 builder, 34/67/6B decoders and B2 max HP.
Collection operations, original icon-bank group lookups, C++ strings and
Windows graphical refresh are declared fixture boundaries. Real UI proof is
separate and uses only mouse input and read-only original-client probes.
"""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESP
from emulate_item_use import UseFixture
from world_inventory_packets import inventory_notice,transaction_reply,parse_item_move_request
from world_item_use_packets import vitals_notice

class EquipmentFixture(UseFixture):
    def __init__(self,binary):
        self.gears={};super().__init__(binary)
    def on_code(self,uc,va,size,context):
        sp=uc.reg_read(UC_X86_REG_ESP);obj=uc.reg_read(UC_X86_REG_ECX)
        if va==0x46eaf0:
            kind,offset=self.read32(sp+4),self.read32(sp+8)
            self.ret({2:1,3:857,8:3805}.get(kind,0)+offset)
        elif va in (0x5525c0,0x5525d0):self.ret(1,24 if va==0x5525c0 else 4)
        elif va==0x51ed60:self.gears[obj]={};uc.mem_write(obj,bytes(16));self.ret()
        elif va==0x51ee00:
            slot,item=self.read32(sp+4),self.read32(sp+8)
            self.gears.setdefault(obj,{})[slot]=item;self.ret(0,12)
        elif va==0x51e470:
            identity=bytes(uc.mem_read(self.read32(sp+4),16))
            self.ret(next((p for p in self.gears.get(obj,{}).values() if bytes(uc.mem_read(p,16))==identity),0),4)
        elif va==0x51edf0:
            self.gears[obj]=self.gears.get(self.read32(sp+4),{}).copy();self.ret(obj,4)
        else:super().on_code(uc,va,size,context)

def run(binary):
    f=EquipmentFixture(binary);identity=(0x71000001,1,1,0);p=0x10e3000
    f.uc.mem_write(p,struct.pack('<IIII',*identity));f.uc.mem_write(p+32,bytes(16))
    f.invoke(0x4f6ba0,(p,2,0,1,4,1,p+32,0),this=f.command)
    equip=parse_item_move_request(f.trade_packets[-1])
    assert equip['source_location']==2 and equip['destination_location']==4 and equip['destination_slot']==1 and equip['count']==1
    item={'identity':identity,'catalog_index':0,'slot':1,'location':4,'definition_key':'test-sword','quantity':1,'name':'Local Test Sword','buy_price':0,'sell_price':0}
    snapshot={'money':5000,'capacity':32,'items':[],'equipment':[item]}
    # Original 67 deliberately decodes all definitions into a temporary bag;
    # its original 4D record then clones the item to location4/body slot1.
    f.write32(f.command+0x10,1)
    f.receive(0x52b86b,transaction_reply(equip['sequence'],5000,snapshot=snapshot))
    gear=0x10e6000;ptr=f.gears[gear][1]
    assert f.read32(f.command+0x10)==0 and f.read32(ptr+0x1c)==4 and f.read32(ptr+0x20)==2 and f.read32(ptr+0x30)==1
    assert f.item_strings[ptr+0x34]=='Local Test Sword'
    f.receive(0x52b8ef,inventory_notice((1,1),0x1120108,snapshot))
    assert list(f.gears[gear])==[1] and not f.collections[f.inventory]
    f.receive(0x52ca9b,vitals_notice((1,1),0x1120108,{'hp':100,'tp':30,'max_hp':110,'max_tp':30}))
    assert f.read32(f.profile+0xa8)==110 and f.read32(f.profile+8)==100
    f.invoke(0x4f6ba0,(p,4,1,0xffffffff,2,0xffffffff,p+32,0),this=f.command)
    unequip=parse_item_move_request(f.trade_packets[-1]);assert unequip['source_location']==4 and unequip['destination_slot']==-1
    initial=EquipmentFixture(binary)
    from world_map_packets import world_initialization_reply
    from character_store import native_character_fields
    initial.invoke(0x4db8f0,this=initial.data+0x488)
    packet=world_initialization_reply((1,1),'Archive',native_character_fields((1,1),'Archive',(1,1,0,0,0,0,0,0,0,0)),1,inventory=snapshot)
    initial.uc.mem_write(0x109a000,packet);initial.invoke(0x43f090,(0x109a000,0x109a028),this=initial.ui)
    assert list(initial.gears[initial.data+0x488])==[1] and not initial.assertions and not f.assertions
    return {'passed':True,'native_equip_request':equip,'native_unequip_request':unequip,'native_67_location4_item_name':'Local Test Sword','native_gear_slot':1,'native_icon_id':1,'native_gear_type':4,'native_gear_mask':2,'native_pending_released':True,'native_initial_34_gear_restored':True,'native_notice_6b_gear_restored':True,'native_b2_max_hp':110,'assertions':f.assertions+initial.assertions,'provenance':'Explicit offline test equipment; original official templates and combat appearance unresolved','substitutions':['Inherited OS/transport/string lifetime boundaries','Bag and keyed equipment collection boundaries','Measured original ICND resource lookup boundaries','Windows equipment refresh lifetime boundary; no UI claim from this fixture']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    Path(a.out).write_text(json.dumps(run(a.binary),indent=2));print('ORIGINAL_EQUIPMENT_BUILDER_34_67_6B_B2_PASS')
