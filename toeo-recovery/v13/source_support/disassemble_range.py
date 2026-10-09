"""Reproduce a bounded Capstone listing for the preserved original client."""
import argparse
import hashlib
from pathlib import Path
import pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from emulate_session_bootstrap import EXPECTED_SHA256

p=argparse.ArgumentParser()
p.add_argument('binary');p.add_argument('start',type=lambda x:int(x,0))
p.add_argument('length',type=lambda x:int(x,0));p.add_argument('output')
a=p.parse_args();raw=Path(a.binary).read_bytes()
if hashlib.sha256(raw).hexdigest()!=EXPECTED_SHA256:raise SystemExit('Client SHA256 mismatch')
if not 0<a.length<=65536:raise SystemExit('Request a bounded range of 1..65536 bytes')
im=pefile.PE(data=raw).get_memory_mapped_image();offset=a.start-0x400000
if offset<0 or offset+a.length>len(im):raise SystemExit('Range outside original PE image')
dis=Cs(CS_ARCH_X86,CS_MODE_32)
Path(a.output).write_text('\n'.join(f'{i.address:08x} {i.mnemonic:8} {i.op_str}'
                                 for i in dis.disasm(im[offset:offset+a.length],a.start)),encoding='utf-8')
