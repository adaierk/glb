"""Original enqueue, serializer, NNet frame builder and response correlator.

Fixture explicitly selects the supported plain transport branch. Actual Windows
startup may select compression/encryption, which remains to be measured.
"""
import argparse
import json
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_EIP
from emulate_account_login import AccountFixture
from emulate_session_bootstrap import NativeFixture, EXPECTED_SHA256
from account_packets import message, login_ok_body, login_request
from native_handshake_packets import bootstrap402, user_record
from native_data_packets import data405, parse405


class TransportFixture(AccountFixture):
    def __init__(self, binary):
        self.transport = False
        super().__init__(binary, bootstrap402(records=[user_record(2,2,1),user_record(1,1,2)]))
        self.frames = []
        self.module = 0x1022000
        self.info = 0x1023000
        self.write32(self.wrapper,0x708614)
        self.write32(self.wrapper+8,self.module)
        self.write32(self.wrapper+0x10,self.login)
        self.write32(self.wrapper+0x34,0x1024000)
        self.write32(self.wrapper+0x38,4096)
        self.write32(self.wrapper+0x3c,1024)
        self.write32(self.wrapper+0x40,1024)
        self.write32(self.wrapper+0x44,0x622960)  # constructor's original compression callback
        self.write32(self.wrapper+0x4c,0x622ac0)  # constructor's original decompression callback
        self.write32(self.module+8,self.info)  # startup request pool, empty linked free node
        self.write32(self.module+0x20,self.module+0x20)
        self.write32(self.module+0x24,self.module+0x20)
        self.write32(self.module+0x28,self.conn)
        self.write32(self.module+0x3c,1)
        self.write32(0x7cfe4c,1)  # native request ID counter initialization
        self.write32(self.net,1)  # native client system type
        self.write32(self.conn+0x58,4096)
        self.write32(self.conn+0x7c,0x1020000)
        self.write32(self.conn+0x80,4096)
        self.write32(self.conn+0x88,0x622870)
        self.write32(self.conn+0x8c,self.wrapper)
        self.write32(self.conn+0x90,0x622890)
        self.write32(self.conn+0x94,self.wrapper)
        self.write32(self.conn+0x194,self.conn+0x1c0)  # empty deferred frame queue
        owner = self.read32(self.conn+0xc)
        self.write32(owner+0x2c,0x1021000)
        self.write32(0x100e010,0x100e010)
        self.write32(0x100e014,0x100e010)
        self.write32(0x80b744,0x100e010)  # native info observer list sentinel
        self.transport = True
        self.write32(self.conn+0xb0,0x8002)  # startup target, not current state
        self.write32(self.conn+0xf8,1000)
        self.uc.mem_write(0x80b758,b'\x01')  # fixture selects supported TCP-only mode
        self.invoke(0x615dd0,(0,),this=self.conn)
        assert self.read32(self.conn+0x60)==0x8002  # assigned by original sender, not fixture

    def on_code(self,uc,address,size,_):
        if not self.transport:
            return super().on_code(uc,address,size,_)
        if address == 0x60c950:
            sp=uc.reg_read(UC_X86_REG_ESP)
            p = self.read32(sp+8)
            n = self.read32(sp+12)
            self.frames.append(bytes(uc.mem_read(p,n)))
            self.events.append({'event':'native_frame_built','address':hex(address),'bytes':n})
            self.ret(1,20)  # socket enqueue boundary, AFTER original routing/header stamping
        elif address == 0x6bb460:
            p=uc.reg_read(UC_X86_REG_ECX)
            self.uc.mem_write(p,struct.pack('<Q',1000))
            self.ret()
        elif address in (0x6baa22,0x6ba9d0):
            self.ret()  # CRT free; fixture heap has monotonic lifetime
        elif address == 0x5f0bbc:
            super().on_code(uc,address,size,_)
        elif address in (0x61b2a0,0x61dbac):
            super().on_code(uc,address,size,_)
        else:
            NativeFixture.on_code(self,uc,address,size,_)

    def request(self,username='archive001',password='local123'):
        user,pw=0x1014000,0x1015000
        self.uc.mem_write(user,username.encode('cp932')+b'\x00')
        self.uc.mem_write(pw,password.encode('cp932')+b'\x00')
        self.invoke(0x620d80,(user,pw))
        assert self.read32(self.login+0x18)==2
        assert self.read32(self.login+0xc0)==self.info
        payload=bytes(self.uc.mem_read(self.read32(self.info+0x30),149))
        expected=bytearray(login_request(username,password))
        expected[5:9]=struct.pack('<I',1)
        assert payload==bytes(expected)
        assert self.read32(self.info+0x28)==1
        return payload

    def route_reply(self,reply,request_id=1):
        self.uc.mem_write(self.answer,reply)
        sp=0x20ff000
        self.uc.mem_write(sp,struct.pack('<IIII',self.stop,0,self.answer,len(reply)))
        self.uc.reg_write(UC_X86_REG_ESP,sp)
        self.uc.reg_write(UC_X86_REG_ECX,self.wrapper)
        self.uc.emu_start(0x61fdf0,self.stop,count=200000)
        if self.uc.reg_read(UC_X86_REG_EIP)!=self.stop:
            raise RuntimeError('Reply routing did not return')
        transport_status=bytes(self.uc.mem_read(self.info+0x14,1))[0]
        self.invoke(0x61d9e0)
        result=self.read32(self.login+0x20)
        return {'transport_status':transport_status,'login_status':self.read32(self.login+0x18),
                'result':hex(result),'account_id':self.read32(result+0x48) if result else None,
                'login_sid':self.read32(result+0x4c) if result else None,
                'assertions':self.assertions,'events':self.events}

    def receive_frame(self,reply):
        frame=data405(reply,0,2,1,1)
        self.dispatch(frame)  # full original 0x405 -> callback -> correlator path
        transport_status=bytes(self.uc.mem_read(self.info+0x14,1))[0]
        self.invoke(0x61d9e0)
        result=self.read32(self.login+0x20)
        return {'transport_status':transport_status,'login_status':self.read32(self.login+0x18),
                'account_id':self.read32(result+0x48) if result else None,
                'login_sid':self.read32(result+0x4c) if result else None,'assertions':self.assertions,
                'reply_frame_hex':frame.hex(),'events':self.events}


def run(binary):
    f=TransportFixture(binary); request=f.request()
    native_frame=f.frames[0]
    assert native_frame==data405(request,1,1,route=0xffef,target_index=0,target_uid=0)
    assert parse405(native_frame)['opcode']==0x20
    result=f.receive_frame(message(0x21,login_ok_body(),request_id=1))
    assert result['transport_status']==2
    assert result['login_status']==1
    assert result['account_id']==1 and result['login_sid']==1
    assert not f.assertions
    wrong=TransportFixture(binary);wrong.request()
    bad_id=wrong.receive_frame(message(0x21,login_ok_body(),request_id=2))
    assert bad_id['transport_status']==1 and bad_id['login_status']==2
    assert not wrong.assertions
    return {'original_sha256':EXPECTED_SHA256,'passed':True,
            'level':'original_send_and_receive_NNet_data_path_to_account_login_state',
            'request_hex':request.hex(),'frame_hex':[p.hex() for p in f.frames],'result':result,
            'wrong_request_id':bad_id,
            'substitutions':['CRT heap allocation/free','security cookie','assertion logger (none triggered)',
                             '6bb460 OS clock','60c950 socket enqueue boundary after native header stamping'],
            'fixture':['Original bootstrap and original connecting-to-ready sender','startup request pool and packet buffers',
                       'supported global transport mode 1 (TCP-only); real startup mode not assumed',
                       'server record FIRST, own user SECOND',
                       'original constructor compression callbacks; uncompressed message flags; cipher object NULL'],
            'does_not_prove':['Actual Windows crypto/compression mode','Windows GUI','character list','playable game']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();r=run(a.binary)
    Path(a.out).write_text(json.dumps(r,indent=2),encoding='utf-8')
    print('ORIGINAL_X86_ACCOUNT_TRANSPORT_PASS')
