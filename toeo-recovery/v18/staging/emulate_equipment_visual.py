"""Unchanged 3A/43/44/45/6C readers and world clothing refresh.
Only C++ tree storage/copy, OS/UI lifetime and model-resource loading are
fixture boundaries. No parser results or component fields are manufactured.
"""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESP,UC_X86_REG_EIP
from emulate_equipment import EquipmentFixture
from world_equipment_visual_packets import equipment_visual_records,equipment_visual_notice
from world_inventory_packets import inventory_records,transaction_reply
from world_map_packets import world_initialization_reply
from character_store import native_character_fields

class VisualFixture(EquipmentFixture):
    def __init__(self,binary):
        self.visuals={};self.visual_nodes={};self.node_next=0x10ef100;self.layer_calls=[];self.refreshes=0
        super().__init__(binary)
        self.visual=0x10ec000;self.model=0x10ed000
        self.write32(self.player+0x1e0,self.visual);self.write32(self.player+0x158,self.model)
        self.invoke(0x4db8f0,this=self.visual)
        self.visuals[self.visual]={}
    def on_code(self,uc,va,size,context):
        sp=uc.reg_read(UC_X86_REG_ESP);obj=uc.reg_read(UC_X86_REG_ECX)
        if va==0x51d320:
            self.visuals[obj]={}
            if not self.read32(obj+4):self.write32(obj+4,0x10ef000)
            self.ret()
        elif va==0x4ba100 and obj in self.visuals:
            out,key=self.read32(sp+4),self.read32(self.read32(sp+8))
            node=self.visual_nodes.get((obj,key),self.read32(obj+4)) if key in self.visuals[obj] else self.read32(obj+4)
            self.write32(out,node);self.ret(out,8)
        elif va==0x51d3e0 and obj in self.visuals:
            out,pair=self.read32(sp+4),self.read32(sp+8)
            key,item=self.read32(pair),self.read32(pair+4)
            self.visuals[obj][key]=item
            node=self.node_next;self.node_next+=32
            self.write32(node+12,key);self.write32(node+16,item);self.visual_nodes[(obj,key)]=node
            self.write32(out,node);self.ret(out,8)
        elif va==0x51d4a0:
            source=self.read32(sp+4);self.visuals[obj]=self.visuals.get(source,{}).copy()
            for key,item in self.visuals[obj].items():
                node=self.node_next;self.node_next+=32
                self.write32(node+12,key);self.write32(node+16,item);self.visual_nodes[(obj,key)]=node
            self.ret(obj,4)
        elif va==0x518280:
            values=[self.read32(sp+i) for i in (4,8,12,16)]
            self.layer_calls.append({'model':obj,'layer':values[0],'resource':values[1],'palette':values[2],'refresh':values[3]});self.ret(1,16)
        elif va==0x518ac0:self.refreshes+=1;self.ret()
        elif va in (0x4ff070,0x4cbcf0):self.ret()
        elif va==0x5b6d60:self.ret(0,4)
        elif va==0x4fe470:self.ret(0,8)
        else:super().on_code(uc,va,size,context)
    def components(self,obj):
        return {key:list(struct.unpack('<IIIIIII',self.uc.mem_read(p,28))) for key,p in self.visuals.get(obj,{}).items()}

def item(key,slot,instance):
    return {'identity':(0x71000000+instance,1,1,0),'catalog_index':0,'slot':slot,'location':4,'definition_key':key,'quantity':1,'name':'Local Test '+('Sword' if slot==1 else 'Body'),'buy_price':0,'sell_price':0}

def run(binary):
    f=VisualFixture(binary);sword=item('test-sword',1,1);body=item('test-body',2,2)
    both={'money':5000,'capacity':32,'items':[],'equipment':[sword,body]}
    f.write32(f.command+0x10,1);f.receive(0x52b86b,transaction_reply(1,5000,snapshot=both))
    assert [f.read32(f.gears[0x10e6000][s]+0xb0) for s in (1,2)]==[10000,4000]
    f.receive(0x52ba8d,equipment_visual_notice((1,1),0x1110101,both))
    actual=f.components(f.visual)
    assert actual=={1:[*sword['identity'],0,10000,2],2:[*body['identity'],0,4000,1]},actual
    active=[x for x in f.layer_calls if x['resource']]
    assert [(x['layer'],x['resource']) for x in active]==[(2,10000),(1,4000)],f.layer_calls
    preview=0x10eb000;f.invoke(0x550b10,(f.player,0),this=preview)
    assert struct.unpack('<III',f.uc.mem_read(preview+12,12))==(1,4000,0)
    assert struct.unpack('<III',f.uc.mem_read(preview+48,12))==(2,10000,0)
    f.layer_calls=[];bare={'money':5000,'capacity':32,'items':[],'equipment':[]}
    f.receive(0x52ba8d,equipment_visual_notice((1,1),0x1110101,bare))
    assert not f.components(f.visual)
    assert [(x['layer'],x['resource']) for x in f.layer_calls]==[(1,200),(2,0),(3,0),(4,0)],f.layer_calls
    f.layer_calls=[];f.receive(0x52ba8d,equipment_visual_notice((1,1),0x1110101,both))
    assert f.components(f.visual)==actual
    initial=VisualFixture(binary);initial.invoke(0x4db8f0,this=initial.data+0x488);initial.invoke(0x4db8f0,this=initial.data+0x494)
    packet=world_initialization_reply((1,1),'Archive',native_character_fields((1,1),'Archive',(1,1,0,0,0,0,0,0,0,0)),1,inventory=both)
    initial.uc.mem_write(0x109a000,packet);initial.invoke(0x43f090,(0x109a000,0x109a028),this=initial.ui)
    assert initial.components(initial.data+0x494)==actual
    assert not f.assertions and not initial.assertions
    return {'passed':True,'native_3a_item_resources':[10000,4000],'native_44_components':actual,'native_world_layers':active,'native_unequip_fallback':[[1,200],[2,0],[3,0],[4,0]],'native_preview_body':[1,4000,0],'native_preview_weapon':[2,10000,0],'native_initial_34_visual_restore':True,'native_6c_equip_unequip_reequip':True,'assertions':f.assertions+initial.assertions,'substitutions':['Inherited explicit equipment fixture boundaries','C++ visual tree storage, lookup, clear and copy','Model loading boundary captures original requested parts','Windows graphical lifetime/refresh boundary'],'limitations':['Native GUI and asset rendering are verified separately','Resource IDs are original symbols; gear-to-resource mapping is an explicit local fixture']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    try:r=run(a.binary)
    except Exception as e:raise
    Path(a.out).write_text(json.dumps(r,indent=2));print('ORIGINAL_EQUIPMENT_VISUAL_RECORDS_WORLD_PREVIEW_RESTORE_PASS')
