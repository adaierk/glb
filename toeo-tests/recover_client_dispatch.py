#!/usr/bin/env python3
"""Read-only original Tales of Eternia Online client parser forensics."""
import argparse,collections,hashlib,json
from pathlib import Path
import pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_32,CS_OP_IMM
ANCHORS={'recv_call':0x608cd4,'recv_result':0x608ce3,'header_swap':0x60b030,
'magic_write':0x60b186,'rx_entry':0x619a10,'state_entry':0x6143d0,
'after_recv':0x61452f,'min_18':0x6145e7,'header_word':0x61462d,
'packet_len':0x614673,'need_more':0x614f14,'assembler':0x60e1e0,
'decode':0x6bee00,'dispatch':0x6c0b30,'tail_write':0x611cfb}
BLOCKS=[('recv',0x608c60,0x210),('endianness',0x60afc0,0x290),
('frame_header_write',0x60b100,0x300),('state_a',0x614310,0x510),
('state_b',0x6148a0,0x780),('assembler',0x60e130,0x3b0),
('rx_method',0x619970,0x300),('decoder',0x6bed90,0x420),
('dispatcher',0x6c0ad0,0x390),('tail',0x611c40,0x220)]
def main():
 a=argparse.ArgumentParser()
 a.add_argument('original');a.add_argument('--out',required=True)
 args=a.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 raw=Path(args.original).read_bytes();pe=pefile.PE(data=raw,fast_load=True)
 base=pe.OPTIONAL_HEADER.ImageBase
 print('ORIGINAL',args.original,'SHA256',hashlib.sha256(raw).hexdigest(),'BASE',hex(base),flush=True)
 md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;blocks=[]
 for name,va,n in BLOCKS:
  print('\n=== BLOCK',name,hex(va),flush=True)
  rows=[]
  for ins in md.disasm(pe.get_data(va-base,n),va):
   near=[k for k,v in ANCHORS.items() if v==ins.address]
   rows.append([hex(ins.address),ins.bytes.hex(),ins.mnemonic,ins.op_str,near])
   print('%08x  %-30s %-8s %s%s'%(ins.address,ins.bytes.hex(' '),ins.mnemonic,ins.op_str,(' [ANCHOR '+','.join(near)+']') if near else ''))
  blocks.append({'name':name,'rows':rows})
 refs=collections.defaultdict(list)
 print('\n=== XREFS',flush=True)
 for s in pe.sections:
  if not(s.Characteristics&0x20000000):continue
  md.skipdata=True
  for ins in md.disasm(s.get_data(),base+s.VirtualAddress):
   if ins.mnemonic.startswith(('call','j')) and ins.mnemonic!='.byte' and ins.operands and ins.operands[0].type==CS_OP_IMM:
    dst=ins.operands[0].imm&0xffffffff
    if any(abs(dst-v)<128 for v in ANCHORS.values()):refs[hex(dst)].append(hex(ins.address)+' '+ins.mnemonic)
  md.skipdata=False
 for k,v in sorted(refs.items()):print(k,len(v),v[:25])
 print('\n=== MARKERS',flush=True)
 for s in pe.sections:
  if not(s.Characteristics&0x20000000):continue
  data=s.get_data()
  for pat in (bytes.fromhex('78563412'),bytes.fromhex('12345678')):
   off=0
   while True:
    i=data.find(pat,off)
    if i<0:break
    print(hex(base+s.VirtualAddress+i),pat.hex(),data[max(0,i-12):i+24].hex())
    off=i+1
 (out/'dispatch_static.json').write_text(json.dumps({'image_base':base,'blocks':blocks,'refs':refs},indent=1),encoding='utf-8')
 print('STATIC_FORENSIC_COMPLETED',flush=True)
if __name__=='__main__':main()
