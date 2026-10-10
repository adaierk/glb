"""Read unchanged original x86 battle/actor protocols; no game-memory modifications."""
import hashlib,json,re,struct,subprocess,os,sys
from pathlib import Path
import pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
ROOT=Path.cwd();OUT=ROOT/'toeo-recovery/v19/research';OUT.mkdir(parents=True,exist_ok=True)
pack=Path(os.environ['RUNNER_TEMP'])/'TOEO_ORIGINAL/client_pack.7z'
raw=Path(os.environ['RUNNER_TEMP'])/'TOEO_V19_RAW'
subprocess.run(['7z','x','-y','-o'+str(raw),str(pack),'DefaultComponent/ToEO_CL.dat','NewComponent1/resource/cid0.idt','NewComponent1/resource/cid1.idt','NewComponent1/resource/crsid.crs','NewComponent1/resource/e000.cpd','NewComponent1/resource/e001.cpd'],check=True,stdout=subprocess.DEVNULL)
data=(raw/'DefaultComponent/ToEO_CL.dat').read_bytes()
assert hashlib.sha256(data).hexdigest()=='635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'
pe=pefile.PE(data=data);base=pe.OPTIONAL_HEADER.ImageBase
cs=Cs(CS_ARCH_X86,CS_MODE_32);cs.skipdata=True
def dis(va,size):return '\n'.join(f'{i.address:08x}  {i.mnemonic:8s} {i.op_str}' for i in cs.disasm(pe.get_data(va-base,size),va))
ranges={
 'world_dispatch_head':(0x52a580,0x200),
 'world_protocol_dispatch':(0x52a580,0x61c0),
 'actor_factory_records':(0x51c1e0,0x1100),
 'world_command_builders':(0x4f5700,0x3800),
 'world_mouse_actions':(0x505900,0x1600),
 'npc_command_builders':(0x522700,0x1500),
 'battle_model_interface':(0x40c600,0xc00),
}
for name,(va,length) in ranges.items():(OUT/(name+'.txt')).write_text(dis(va,length))
signals=[]
for encoding,pattern in [('ascii',rb'[\x20-\x7e]{5,}'),('utf-16le',rb'(?:[\x20-\x7e]\x00){5,}')]:
 for m in re.finditer(pattern,data):
  text=m.group().decode(encoding)
  if re.search('battle|attack|enemy|monster|encount|skill',text,re.I):
   try:va=base+pe.get_rva_from_offset(m.start())
   except Exception:continue
   signals.append({'address':hex(va),'text':text[:260]})
(OUT/'battle_symbols.json').write_text(json.dumps(signals,indent=2))
# Original opcode table operands and surrounding instructions; tables are decoded after inspection.
head=list(cs.disasm(pe.get_data(0x52a580-base,0x200),0x52a580))
(OUT/'dispatch_head.json').write_text(json.dumps([{'address':hex(i.address),'instruction':i.mnemonic+' '+i.op_str} for i in head],indent=2))
targets={0x51c1e0:'actor_create',0x40cad0:'battle_visual_layer',0x4fef50:'world_visual',0x4ff070:'battle_visual'}
refs=[]
for sec in pe.sections:
 if not sec.Characteristics&0x20000000:continue
 body=sec.get_data();start=base+sec.VirtualAddress
 for m in re.finditer(b'\xe8',body):
  at=m.start()
  if at+5>len(body):continue
  dest=(start+at+5+struct.unpack_from('<i',body,at+1)[0])&0xffffffff
  if dest in targets:refs.append({'address':hex(start+at),'target':hex(dest),'kind':targets[dest]})
(OUT/'battle_call_refs.json').write_text(json.dumps(refs,indent=2))
print(json.dumps({'unchanged_exe_sha256':hashlib.sha256(data).hexdigest(),'signals':len(signals),'ranges':len(ranges),'references':len(refs)}))
