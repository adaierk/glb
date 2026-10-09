"""Cross-check translated CNLzComp1 against original encoder and decoder."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX,UC_X86_REG_EIP
from emulate_session_bootstrap import NativeFixture
from native_compression import decompress


class CompressionFixture(NativeFixture):
    def call(self,va,args):
        sp=0x20ff000;self.uc.mem_write(sp,struct.pack('<'+'I'*(len(args)+1),self.stop,*args))
        self.uc.reg_write(UC_X86_REG_ESP,sp);self.uc.reg_write(UC_X86_REG_ECX,0)
        self.uc.emu_start(va,self.stop,count=8000000)
        if self.uc.reg_read(UC_X86_REG_EIP)!=self.stop:raise RuntimeError('Native compression did not return')
        return self.uc.reg_read(UC_X86_REG_EAX)


def run(binary):
    f=CompressionFixture(binary);source=0x1100000;coded=0x1200000;output=0x1300000;count=0x1005000
    cases=[]
    # Repetitive and large mixed streams exercise growing widths and LRU eviction.
    payloads=[bytes.fromhex('80ed0024002c000000000000240000000801120101000000010000000100000001000000'),
        b'abc'*500,b''.join(hashlib.sha256(str(i).encode()).digest()*3 for i in range(250))]
    for payload in payloads:
        f.uc.mem_write(source,payload)
        result=f.call(0x622960,(1,coded,60024,count,source,len(payload),0))
        # Uncompressible messages may be declined by the native wrapper; use
        # its original raw encoder instead, retaining its measured header.
        n=f.read32(coded+8);wrapper=bytes(f.uc.mem_read(coded,16+n))
        assert decompress(wrapper)==payload
        assert f.call(0x622ac0,(output,60000,count,coded,len(wrapper)))==1
        assert f.read32(count)==len(payload) and bytes(f.uc.mem_read(output,len(payload)))==payload
        cases.append({'bytes':len(payload),'coded_bytes':len(wrapper),'native_compress_result':result,
            'sha256':hashlib.sha256(payload).hexdigest()})
    assert not f.assertions
    return {'passed':True,'cases':cases,'assertions':f.assertions,
        'executed':['622960 native wrapper/encoder','622AC0 native wrapper/decoder','5F8660 native raw CRC32'],
        'substitutions':['NativeFixture allocation/cookie/assertion boundaries; no algorithm substitutions']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    result=run(a.binary);Path(a.out).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('ORIGINAL_NATIVE_COMPRESSION_BIDIRECTIONAL_PASS',len(result['cases']))
