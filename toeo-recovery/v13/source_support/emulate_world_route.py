"""Original selected route -> world endpoint conversion, stopping at socket APIs.

No socket success state is claimed. The fixture records the actual original
arguments to the TCP and UDP endpoint functions; maps are not loaded.
"""
import argparse
import json
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESP
from emulate_character_select import SelectFixture
from character_packets import select_character_reply


class RouteFixture(SelectFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.route_manager=0x1050000
        self.route_transport=0x1060000
        self.controller=0x1051000
        self.controller_array=0x1052000
        self.socket_array=0x1052100
        self.endpoint_calls=[]
        self.route_ready=False
        self.write32(self.netstate+0x4c,self.controller)
        self.uc.mem_write(self.netstate+0x34,b'\x01')
        self.write32(self.controller+4,self.controller_array)
        self.write32(self.controller+8,self.controller_array+4)
        self.write32(self.controller_array,self.route_manager)
        self.write32(self.route_manager+8,self.route_transport)
        self.write32(self.route_transport+0x1c,self.socket_array)
        self.write32(self.route_transport+0x20,self.socket_array+20)
        for i in range(5):self.write32(self.socket_array+i*4,0x1053000+i*256)
        self.write32(0x6e2508,0x104f050)  # CRT memmove

    def on_code(self,uc,address,size,_):
        if address==0x104f050:
            sp=uc.reg_read(UC_X86_REG_ESP)
            dest,source,n=(self.read32(sp+i) for i in (4,8,12))
            if n:uc.mem_write(dest,bytes(uc.mem_read(source,n)))
            self.ret(dest)
        elif address==0x6072e0:
            sp=uc.reg_read(UC_X86_REG_ESP)
            dest=self.read32(sp+4)
            fmt=self.read32(sp+8)
            assert bytes(uc.mem_read(fmt,12)).split(b'\0')[0]==b'%d.%d.%d.%d'
            host='.'.join(str(self.read32(sp+off)) for off in (12,16,20,24))
            uc.mem_write(dest,host.encode()+b'\0')
            self.ret(len(host))  # CRT formatting only
        elif address in (0x6be740,0x6c1690):
            sp=uc.reg_read(UC_X86_REG_ESP)
            p=self.read32(sp+4)
            raw=bytes(uc.mem_read(p,64)).split(b'\0')[0]
            self.endpoint_calls.append({'transport':'udp' if address==0x6be740 else 'tcp',
                                        'host':raw.decode(),'port':self.read32(sp+8),
                                        'identity':[self.read32(sp+12),self.read32(sp+16)]})
            self.ret(1,16)  # endpoint boundary; only allows original route conversion to finish
        elif address==0x6ab6d5:
            self.route_ready=True
            uc.emu_stop()  # before controller trees/socket lifecycle; no fake native ready state
        else:super().on_code(uc,address,size,_)

    def convert_selected(self):
        self.select_result=None
        sp=0x20ff000
        links=self.read32(self.selected+0x4c);n=self.read32(self.selected+0x44)
        self.uc.mem_write(sp,struct.pack('<IIIII',self.stop,links,n,self.read32(self.selected),self.read32(self.selected+4)))
        self.uc.reg_write(UC_X86_REG_ESP,sp)
        self.uc.reg_write(UC_X86_REG_ECX,self.netstate)
        self.uc.emu_start(0x5308e0,self.stop,count=300000)
        assert self.route_ready and not self.assertions
        return self.endpoint_calls


def run(binary):
    # Entry IP is little-endian inet_aton bytes; +4 is UDP port, +8 TCP port.
    cases={}
    for host,ip in [('127.0.0.1',0x0100007f),('10.20.30.40',0x281e140a)]:
        f=RouteFixture(binary);f.request_selection()
        f.receive_selection(select_character_reply((987,654,123,456,0,0,0,0,0),[(ip,45002,11101)]))
        calls=f.convert_selected()
        assert calls==[{'transport':'udp','host':host,'port':45002,'identity':[123,456]}]
        # Original mode 2 starts parallel UDP endpoints. Explicitly test fallback TCP conversion too.
        f.route_ready=False;f.endpoint_calls=[]
        f.invoke(0x6aa950,(0,0),this=f.route_transport)
        assert f.endpoint_calls==[{'transport':'tcp','host':host,'port':11101,'identity':[123,456]}]
        cases[host]={'initial_endpoint':calls,'fallback_endpoint':f.endpoint_calls,'assertions':f.assertions}
    return {'passed':True,'level':'original_selection_reply_route_vector_to_world_endpoint_arguments',
            'cases':cases,'recovered_link_fields':['IP bytes (inet_aton, little endian DWORD)','UDP port DWORD','TCP port DWORD'],
            'substitutions':['inherited fixture boundaries','CRT memmove/formatting',
                             'UDP endpoint 6be740 and TCP endpoint 6c1690 return 1 only at socket boundary'],
            'does_not_prove':['actual socket connection','world authentication','map load','Windows event loop','playability']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();r=run(a.binary)
    Path(a.out).write_text(json.dumps(r,indent=2),encoding='utf-8')
    print('ORIGINAL_X86_WORLD_ENDPOINT_ARGUMENTS_PASS')
