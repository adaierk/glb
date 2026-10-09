"""Execute original table generation, encrypt/decrypt and corruption rejection."""
import argparse
import json
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EAX
from emulate_world_completion import CompletionFixture
from native_cipher import PERM,INV,KEY,encode,decode

class CipherFixture(CompletionFixture):
    def __init__(self,binary,padding):
        self.padding=padding
        super().__init__(binary)
        self.uc.mem_map(0,4096)  # Original constructor's FS:[0] SEH chain.
        obj=0x1090000
        self.write32(obj+0x204,0x1091000);self.write32(obj+0x208,0x1092000)
        self.invoke(0x622420,this=obj)
        assert bytes(self.uc.mem_read(0x1091000,256))==PERM
        assert bytes(self.uc.mem_read(0x1092000,256))==INV
        self.write32(0x7d0244,0x1091000);self.write32(0x7d0248,0x1092000)
        self.crc,self.input,self.output,self.decoded=0x1093000,0x1095000,0x1096000,0x1098000
        self.uc.mem_write(0x109a000,b'\xc3');self.write32(0x6e27fc,0x109a000)
        self.write32(self.crc+4,0x1094000);self.write32(self.crc+8,256)
        for i in range(256):
            c=i
            for _ in range(8):c=(c>>1)^(0xedb88320 if c&1 else 0)
            self.write32(0x1094000+i*4,c)

    def on_code(self,u,a,s,x):
        if a==0x5f4fe0:self.ret(self.padding) # Explicit randomness boundary only.
        elif a==0x109a000:self.ret(123456) # GetTickCount IAT boundary.
        else:super().on_code(u,a,s,x)

    def encrypt(self,payload,tick):
        self.uc.mem_write(self.input,payload)
        self.invoke(0x622930,(self.crc,self.output,8192,self.input,len(payload),KEY,tick))
        return bytes(self.uc.mem_read(self.output,self.uc.reg_read(UC_X86_REG_EAX)))

    def decrypt(self,wire):
        self.uc.mem_write(self.output,wire)
        self.invoke(0x622900,(self.crc,self.decoded,8192,self.output,len(wire),KEY))
        n=self.uc.reg_read(UC_X86_REG_EAX)
        return bytes(self.uc.mem_read(self.decoded,n)) if n else None

def run(binary):
    cases=[]
    for padding,tick,n in [(0,0,9),(3,123456,149),(11,0xffffffff,176),(5,0x700100,1024)]:
        f=CipherFixture(binary,padding)
        payload=bytes((i*37)&255 for i in range(n))
        wire=f.encrypt(payload,tick)
        assert wire==encode(payload,tick,padding)
        assert decode(wire)==payload and f.decrypt(wire)==payload
        bad=bytearray(wire);bad[0]^=1
        assert f.decrypt(bytes(bad)) is None
        try:decode(bytes(bad))
        except ValueError:pass
        else:raise AssertionError('Corrupt packet accepted')
        assert not f.assertions
        cases.append({'plain_bytes':n,'wire_bytes':len(wire),'padding_draw':padding,'tick':tick})
    from account_packets import message,login_ok_body
    from native_data_packets import data405,parse405
    f=CipherFixture(binary,3)
    f.write32(f.login+8,f.wrapper);f.write32(f.login+0x20,0);f.write32(f.wrapper+0x14,f.crc)
    f.request()
    assert parse405(f.frames[-1])['opcode']==0x20
    f.dispatch(data405(encode(message(0x21,login_ok_body(),1),12345),0,2,1,1))
    f.invoke(0x61d9e0)
    assert f.read32(f.login+0x18)==1 and not f.assertions
    return {'passed':True,'cases':cases,'encrypted_native_login_result':1,'executed':['622420 original permutation generator','622930 original encoder','622900 original decoder','original CRC corruption rejection','original encrypted login serializer, transport filter, correlator and account handler'],
            'substitutions':['random padding draw','CRT allocation/free, clock and cookie boundaries from inherited native fixture'],
            'limitations':['Does not verify Windows network routing or map entry']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    r=run(a.binary);Path(a.out).write_text(json.dumps(r,indent=2));print('ORIGINAL_CIPHER_BIDIRECTIONAL_PASS')
