"""Original creation/name/SHA-1 builder and creation/deletion response branches."""
import argparse
import json
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX
from emulate_character_list import CharacterFixture
from character_mutation_packets import create_character_request,delete_character_request,mutation_reply,parse_create_request
from native_data_packets import data405


class MutationFixture(CharacterFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.profile=0x1045000
        self.write32(self.fields+0x17c,self.profile)
        self.write32(0x6e2514,0x104f040)  # CRT wcslen boundary
        self.mutation_result=None

    def on_code(self,uc,address,size,_):
        if address==0x104f040:
            p=self.read32(uc.reg_read(UC_X86_REG_ESP)+4);n=0
            while n<32 and bytes(uc.mem_read(p+2*n,2))!=b'\0\0':n+=1
            self.ret(n)
        elif address in (0x438ce2,0x438ab3,0x438a82,0x438e3c,0x438e40):
            self.mutation_result='accepted' if address in (0x438ce2,0x438e3c) else 'rejected'
            uc.emu_stop()  # MFC UI transition/text after native protocol result
        else:super().on_code(uc,address,size,_)

    def request_create(self,name='ArchiveHero',parameters=(1,1,0,0,0,0,0,0,0,1)):
        self.invoke(0x51f930,this=self.profile)
        self.uc.mem_write(0x1047000,name.encode('utf-16le')+bytes(2))
        self.invoke(0x435350,(0x1047000,),this=self.profile+8)
        for off,value in zip((0x54,0x50,0x58,0x5c,0x60,0x64,0x68,0x6c,0x70,0x74),parameters):
            self.write32(self.profile+off,value)
        self.invoke(0x435ad0,this=self.ui)
        actual=self.frames[-1][36:-4]
        assert actual==create_character_request(name,parameters,request_id=1)
        return actual

    def request_delete(self,identity=(123,456)):
        self.write32(self.fields+0x180,identity[0]);self.write32(self.fields+0x184,identity[1])
        self.invoke(0x435d50,this=self.ui)
        actual=self.frames[-1][36:-4]
        assert actual==delete_character_request(identity,request_id=1)
        return actual

    def receive_mutation(self,answer,kind):
        self.dispatch(data405(answer,0,2,1,1))
        assert bytes(self.uc.mem_read(self.info+0x14,1))==b'\x02'
        assert self.read32(self.info+0x2c)==12
        sp=0x20ff000;self.uc.mem_write(sp,struct.pack('<II',self.stop,self.context))
        self.uc.reg_write(UC_X86_REG_ESP,sp);self.uc.reg_write(UC_X86_REG_ECX,self.ui)
        self.uc.emu_start(0x4389b0 if kind=='create' else 0x438db0,self.stop,count=200000)
        if self.mutation_result is None:raise RuntimeError('Mutation handler missed result branch')
        return {'branch':self.mutation_result,'assertions':self.assertions}


def run(binary):
    cases={};samples=[]
    for name,parameters in [('ArchiveHero',(1,1,0,0,0,0,0,0,0,1)),
                            ('テスト',(7,2,1,2,3,4,5,6,7,1)),('a'*31,(2,1,0,0,0,0,0,0,0,1))]:
        f=MutationFixture(binary);r=f.request_create(name,parameters)
        assert parse_create_request(r)['name']==name and not f.assertions
        samples.append({'name':name,'hex':r.hex()})
    for kind,op in [('create',0x38),('delete',0x3a)]:
        for status in (0,1,-1):
            f=MutationFixture(binary)
            f.request_create() if kind=='create' else f.request_delete()
            r=f.receive_mutation(mutation_reply(op,status=status),kind)
            assert r['branch']==('accepted' if status in (0,1) else 'rejected') and not r['assertions']
            cases[f'{kind}_{status}']=r
    return {'passed':True,'level':'original_name_codec_SHA1_mutation_builders_receive_filter_correlation_result_branches',
            'create_samples':samples,'cases':cases,
            'substitutions':['inherited CRT/clock/socket and MFC fixture boundaries','CRT wcslen'],
            'does_not_prove':['MFC follow-up task','character rendering','map entry or playability']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();r=run(a.binary)
    Path(a.out).write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8')
    print('ORIGINAL_X86_CHARACTER_CREATE_DELETE_PASS')
