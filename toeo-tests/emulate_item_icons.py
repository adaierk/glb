"""Execute original ICND fixup and named-group lookup without graphics.

Only the CRT case-insensitive ASCII comparison is substituted. Original bytes,
6A68B0 fixup and 68FF10 lookup run unchanged; this does not prove GUI rendering.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_EIP
from emulate_session_bootstrap import NativeFixture, EXPECTED_SHA256


class IconFixture(NativeFixture):
    def __init__(self, binary, bank):
        super().__init__(binary)
        self.bank = 0x3000000
        self.uc.mem_map(self.bank, (len(bank)+4095)&~4095)
        self.uc.mem_write(self.bank, bank)
        self.provider = 0x10e0000
        self.write32(self.provider+0x50, self.bank)
        self.write32(0x6e25d0, 0x10ef000)

    def on_code(self, uc, va, size, context):
        if va == 0x10ef000:
            sp = uc.reg_read(UC_X86_REG_ESP)
            def string(p):
                b = bytearray()
                while uc.mem_read(p, 1) != b'\0':
                    b.extend(uc.mem_read(p, 1)); p += 1
                    if len(b)>64: raise ValueError('Invalid group name')
                return bytes(b).lower()
            self.ret(0 if string(self.read32(sp+4))==string(self.read32(sp+8)) else 1)
        else: super().on_code(uc, va, size, context)

    def call(self, va, args=(), obj=None):
        sp = 0x20ff000
        self.uc.mem_write(sp, struct.pack('<'+'I'*(1+len(args)), self.stop, *args))
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.reg_write(UC_X86_REG_ECX, self.bank if obj is None else obj)
        self.uc.emu_start(va, self.stop, count=400000)
        if self.uc.reg_read(UC_X86_REG_EIP)!=self.stop: raise RuntimeError('Did not return')
        return self.uc.reg_read(UC_X86_REG_EAX)


def run(binary, bank_path):
    raw = Path(bank_path).read_bytes(); f = IconFixture(binary, raw)
    assert raw[:4]==b'ICND' and f.call(0x6a68b0)&1
    groups=[]
    for i in range(struct.unpack_from('<I', raw, 0x18)[0]):
        p=f.bank+32+i*24
        name=bytes(f.uc.mem_read(p,16)).split(b'\0')[0].decode('ascii')
        f.uc.mem_write(f.packet, name.upper().encode()+b'\0')
        start=f.call(0x68ff10, (f.packet,), obj=f.provider)
        assert start==f.read32(p+16)
        groups.append({'name':name,'start':start,'count':f.read32(p+20)})
    assert next(g for g in groups if g['name']=='Item')=={'name':'Item','start':3805,'count':89}
    f.uc.mem_write(f.packet,b'UNKNOWN\0')
    assert f.call(0x68ff10,(f.packet,),obj=f.provider)==0 and not f.assertions
    return {'passed':True,'original_sha256':EXPECTED_SHA256,'bank_sha256':hashlib.sha256(raw).hexdigest(),
        'groups':groups,'assertions':f.assertions,'native_functions':['6A68B0','68FF10'],
        'substitutions':['CRT ASCII _stricmp only'],'limitations':['Name-to-item associations require separate evidence','No graphical rendering in this fixture']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('bank');p.add_argument('--out',required=True)
    a=p.parse_args();result=run(a.binary,a.bank)
    Path(a.out).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('ORIGINAL_ICND_FIXUP_GROUP_LOOKUP_PASS',len(result['groups']))
