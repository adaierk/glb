"""Compare original creation-preview and selector model-loader argument slices.

Original lookup and original argument loads execute. 518ed0 is stopped before
resource loading; this verifies field projection, not appearance validity.
"""
import argparse
import json
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_ESP,UC_X86_REG_ECX
from emulate_character_mutation import MutationFixture
from character_store import native_character_fields


class FieldFixture(MutationFixture):
    def __init__(self,binary):
        self.slice_stop=None
        self.loader_args=None
        super().__init__(binary)
        self.preview,self.native=0x1049000,0x104a000
        self.write32(self.global_root+0x64,0x1048000)
        self.write32(0x1048000,0x1048200)
        self.write32(self.global_root+0x58,0x1048100)
        self.write32(self.preview+0xec,self.profile)
        self.write32(self.native+0x114,0x1048300)

    def on_code(self,uc,address,size,_):
        if address==self.slice_stop:
            uc.emu_stop()
        elif address==0x434bc0:
            pass  # execute the original model selection, including its fallback switch
        elif address==0x519280:
            self.ret(uc.reg_read(UC_X86_REG_ECX))  # resource-object constructor only
        elif address==0x518ed0:
            sp=uc.reg_read(UC_X86_REG_ESP)
            self.loader_args=[self.read32(sp+4+4*i) for i in range(9)]
            uc.emu_stop()
        else:super().on_code(uc,address,size,_)

    def slice(self,start,stop,esi,eax=0,edi=0,this=0):
        self.slice_stop=stop
        self.uc.mem_write(0x20ff000,struct.pack('<I',self.stop))
        for reg,value in ((UC_X86_REG_ESP,0x20ff000),(UC_X86_REG_EBP,0x20fe000),
                          (UC_X86_REG_ESI,esi),(UC_X86_REG_EAX,eax),
                          (UC_X86_REG_ECX,this),
                          (UC_X86_REG_EDI,edi),(UC_X86_REG_EBX,0)):
            self.uc.reg_write(reg,value)
        self.uc.emu_start(start,self.stop,count=10000)


def run(binary):
    cases=[]
    for params in ((1,1,0,0,0,0,0,0,0,1),(5,2,1,2,3,4,5,6,7,1),(3,1,127,126,0,0,125,0,0,1)):
        f=FieldFixture(binary);f.request_create('ModelCheck',params)
        fields=native_character_fields((123,456),'ModelCheck',params)
        f.uc.mem_write(f.native,fields)
        f.slice(0x5afa63,0x5afa7d,f.preview,eax=f.profile)
        preview_model=f.uc.reg_read(UC_X86_REG_EAX)
        f.slice(0x434c05,0x434c1e,f.native)
        selector_model=f.uc.reg_read(UC_X86_REG_EAX)
        assert preview_model==selector_model and selector_model!=0
        f.slice(0x5afa30,None,f.preview,this=f.preview)
        preview_args=f.loader_args
        assert preview_args is not None
        f.loader_args=None
        f.write32(f.native+0x114,0) # Resource lifetime is outside this projection fixture.
        f.slice(0x434bc0,None,f.native,this=f.native)
        selector_args=f.loader_args
        assert selector_args is not None and preview_args==selector_args and not f.assertions
        cases.append({'parameters':params,'original_model_id':selector_model,
                      'creation_loader_arguments':preview_args,'selection_loader_arguments':selector_args})
    return {'passed':True,'level':'original_lookup_and_pre_resource_model_loader_creation_vs_selection',
            'cases':cases,'unknown_fields':'Other parameters remain stored verbatim, not mapped into world attributes',
            'substitutions':['inherited fixture boundaries','resource-object constructor 519280'],
            'does_not_prove':['518ed0 resource execution','valid appearance index ranges','Windows rendering','playability']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();r=run(a.binary)
    Path(a.out).write_text(json.dumps(r,indent=2),encoding='utf-8')
    print('ORIGINAL_X86_CHARACTER_FIELD_PROJECTION_PASS')
