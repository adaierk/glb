"""Original 0x3b builder and 0x3c route-vector parsing; no map endpoint claim."""
import argparse
import json
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESP
from emulate_character_list import CharacterFixture
from character_packets import select_character_request,select_character_reply
from native_data_packets import data405


class SelectFixture(CharacterFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.selected=0x1046000
        self.write32(self.game+0x28,self.selected)
        self.write32(self.fields+0x48,0x1040000)
        self.write32(self.fields+0x4c,0x1040118)
        self.write32(0x1040018,123)
        self.write32(0x104001c,456)
        self.select_result=None

    def on_code(self,uc,address,size,_):
        if address in (0x43809a,0x437f18):
            self.select_result='accepted' if address==0x43809a else 'rejected'
            uc.emu_stop()  # next connection task requires the Windows event loop
        else:super().on_code(uc,address,size,_)

    def request_selection(self):
        self.invoke(0x436cc0,this=self.ui)
        actual=self.frames[-1][36:-4]
        expected=bytearray(select_character_request((self.read32(0x1040018),self.read32(0x104001c))));expected[5:9]=struct.pack('<I',1)
        assert actual==bytes(expected)
        return actual

    def receive_selection(self,answer):
        self.dispatch(data405(answer,0,2,1,1))
        assert bytes(self.uc.mem_read(self.info+0x14,1))==b'\x02'
        assert self.read32(self.info+0x2c)==112
        sp=0x20ff000
        self.uc.mem_write(sp,struct.pack('<II',self.stop,self.context))
        self.uc.reg_write(UC_X86_REG_ESP,sp)
        self.uc.reg_write(UC_X86_REG_ECX,self.ui)
        self.uc.emu_start(0x437da0,self.stop,count=200000)
        if self.select_result is None:raise RuntimeError('Selection handler did not reach a known result')
        n=self.read32(self.selected+0x44)
        p=self.read32(self.selected+0x4c)
        return {'branch':self.select_result,'route_fields_in_native_storage':
                [self.read32(self.selected+x) for x in (0x24,0x28,0,4,8,12,16,20,24)],
                'links':[list(struct.unpack('<III',self.uc.mem_read(p+12*i,12))) for i in range(n)],
                'assertions':self.assertions}


def run(binary):
    fields=tuple(range(100,109));links=[(10,20,30),(40,50,60)]
    f=SelectFixture(binary);req=f.request_selection()
    good=f.receive_selection(select_character_reply(fields,links))
    f=SelectFixture(binary);f.request_selection()
    bad=f.receive_selection(select_character_reply(fields,links,status=-1))
    assert good['branch']=='accepted' and good['route_fields_in_native_storage']==list(fields)
    assert good['links']==[list(r) for r in links]
    assert bad['branch']=='rejected' and bad['links']==[]
    assert not good['assertions'] and not bad['assertions']
    return {'passed':True,'request_hex':req.hex(),'cases':{'good':good,'server_error':bad},
            'level':'original_character_selection_query_receive_filter_correlation_route_vector_parser',
            'fixture':['fictional character ID and opaque route/link test DWORDs; no live endpoints'],
            'substitutions':'Inherited CRT/clock/socket boundaries; no route/vector parsing is replaced',
            'does_not_prove':['route/link field meanings','subsequent world connection','map loading','playability']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();r=run(a.binary)
    Path(a.out).write_text(json.dumps(r,indent=2),encoding='utf-8')
    print('ORIGINAL_X86_CHARACTER_SELECT_ROUTE_PARSER_PASS')
