"""Original character query, transport/correlator and selector record parser.

MFC CString operations and model-resource loading are explicit substitutions;
no list count, tag, data copy, request ID or acceptance branch is replaced.
"""
import argparse
import json
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESP,UC_X86_REG_ESI
from emulate_game_login import GameFixture
from character_packets import character_list_request,character_list_reply,character_record
from native_data_packets import data405


class CharacterFixture(GameFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.uc.mem_map(0,0x1000)  # Windows SEH thread head, unused in successful paths
        self.role_result=None
        self.names={}
        self.model_loads=0
        self.context,self.vtable,self.task=0x103e000,0x103e100,0x103e200
        self.write32(self.context,self.vtable)
        self.write32(self.context+0x10,1)
        self.write32(self.vtable+0x18,self.task)
        for i,iat in enumerate((0x6e2350,0x6e23c4,0x6e2348,0x6e23bc)):
            self.write32(iat,0x104f000+16*i)

    def on_code(self,uc,address,size,_):
        if address in (0x104f000,0x104f010):
            self.ret(uc.reg_read(UC_X86_REG_ECX))  # MFC CString ctor/dtor
        elif address==0x104f030:
            self.ret(uc.reg_read(UC_X86_REG_ECX),4)  # MFC CString copy constructor
        elif address==0x104f020:
            p=self.read32(uc.reg_read(UC_X86_REG_ESP)+4)
            raw=bytearray()
            while len(raw)<64:
                b=bytes(uc.mem_read(p+len(raw),2))
                if b==b'\0\0':break
                raw.extend(b)
            self.names[uc.reg_read(UC_X86_REG_ECX)]=raw.decode('utf-16le')
            self.ret(uc.reg_read(UC_X86_REG_ECX),4)
        elif address==0x434bc0:
            self.model_loads+=1
            self.ret()  # resource/model construction only, after real record copy
        elif address in (0x43894d,0x43888c):
            self.role_result='accepted' if address==0x43894d else 'rejected'
            self.uc.emu_stop()  # original selector's next UI task requires Windows/MFC
        else:super().on_code(uc,address,size,_)

    def request_characters(self):
        self.invoke(0x438360,this=self.ui)
        actual=self.frames[-1][36:-4]
        expected=bytearray(character_list_request());expected[5:9]=struct.pack('<I',1)
        assert actual==bytes(expected)
        assert self.read32(self.ui+0x20)==self.info
        return actual

    def receive_list(self,answer,count=0):
        self.dispatch(data405(answer,0,2,1,1))
        assert bytes(self.uc.mem_read(self.info+0x14,1))==b'\x02'
        assert self.read32(self.info+0x2c)==len(answer)
        sp=0x20ff000
        self.uc.mem_write(sp,struct.pack('<II',self.stop,self.context))
        self.uc.reg_write(UC_X86_REG_ESP,sp)
        self.uc.reg_write(UC_X86_REG_ECX,self.ui)
        self.uc.emu_start(0x438690,self.stop,count=200000)
        if self.role_result is None:raise RuntimeError('Native selector did not reach an acceptance/rejection branch')
        return {'branch':self.role_result,'available_slots':self.read32(self.fields+0x58),
                'selected_index':self.read32(self.fields+0x54),
                'names':list(self.names.values()),'model_loads_substituted':self.model_loads,
                'native_fields_hex':bytes(self.uc.mem_read(self.read32(self.fields+0x48),0xf8)).hex() if count else None,
                'assertions':self.assertions}


def run(binary):
    f=CharacterFixture(binary);req=f.request_characters()
    empty=f.receive_list(character_list_reply())
    fields=bytearray(0xf8);struct.pack_into('<III',fields,0x14,13,123,456)
    record=character_record(bytes(fields),'ArchiveHero')
    f=CharacterFixture(binary);f.request_characters()
    populated=f.receive_list(character_list_reply([record],2,(123,456)),1)
    f=CharacterFixture(binary);f.request_characters()
    bad=bytearray(character_list_reply([record],2));struct.pack_into('<H',bad,36,0x21)
    wrong_tag=f.receive_list(bytes(bad),1)
    assert empty['branch']=='accepted' and empty['available_slots']==3
    assert populated['branch']=='accepted' and populated['names']==['ArchiveHero']
    assert populated['native_fields_hex']==bytes(fields).hex()
    assert wrong_tag['branch']=='rejected'
    assert all(not c['assertions'] for c in (empty,populated,wrong_tag))
    return {'passed':True,'request_hex':req.hex(),
            'level':'original_query_NNet_receive_correlation_and_character_selector_core',
            'cases':{'empty':empty,'populated':populated,'wrong_record_type':wrong_tag},
            'substitutions':['same transport boundaries as account/game fixtures',
                             'MFC CString construction/destruction/assignment',
                             'model resource construction at 434bc0'],
            'fixture':['SEH thread head; vector allocation and record copying execute original code'],
            'does_not_prove':['valid character job/model appearance','MFC task continuation',
                             'Windows graphical character selection','map entry or playability']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();result=run(a.binary)
    Path(a.out).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('ORIGINAL_X86_CHARACTER_LIST_CORE_PASS')
