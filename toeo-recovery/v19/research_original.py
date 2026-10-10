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

def u32(va):return struct.unpack('<I',pe.get_data(va-base,4))[0]
def jump_table(label,start,count,indices,table):
 idx=pe.get_data(indices-base,count) if indices else bytes(range(count))
 entries=[{'opcode':hex(start+n),'index':v,'handler':hex(u32(table+4*v))} for n,v in enumerate(idx)]
 (OUT/(label+'.json')).write_text(json.dumps(entries,indent=2))
 return entries
ops=jump_table('world_opcodes',0x34,0x192,0x530174,0x52ff04)
jump_table('actor_records',0x22,0xa2,0x51ceb0,0x51ce7c)
jump_table('actor_extensions',0x2e,7,None,0x51cf54)
for row in ops:
 if row['handler']=='0x52fee4':continue
 va=int(row['handler'],16)
 successors=sorted(set(int(x['handler'],16) for x in ops if int(x['handler'],16)>va))
 length=min((successors[0]-va if successors else 0x180),0x1500)
 (OUT/('opcode_'+row['opcode'][2:]+'.txt')).write_text(dis(va,length))
# MSVC TypeDescriptors and Complete Object Locators. These are original data, not inferred class names.
readonly=[s for s in pe.sections if s.Characteristics&0x40000000 and not s.Characteristics&0x20000000]
def pointer_refs(value,sections=None):
 needle=struct.pack('<I',value);found=[]
 for sec in sections or pe.sections:
  b=sec.get_data();offset=0
  while True:
   p=b.find(needle,offset)
   if p<0:break
   found.append(base+sec.VirtualAddress+p);offset=p+1
 return found
rtti=[]
for row in signals:
 if not row['text'].startswith('.?AV'):continue
 if not re.search('TaskBattle|BattleAction|CField|CEnemy|CMonster',row['text']):continue
 descriptor=int(row['address'],16)-8
 locators=[]
 for ref in pointer_refs(descriptor,readonly):
  col=ref-12
  if u32(col)!=0:continue
  for colref in pointer_refs(col,readonly):
   vtable=colref+4
   methods=[u32(vtable+4*n) for n in range(18)]
   if not 0x400000<=methods[0]<0x6e0000:continue
   locators.append({'locator':hex(col),'vtable':hex(vtable),'methods':[hex(v) for v in methods],'vtable_refs':[hex(r) for r in pointer_refs(vtable)]})
   for n,fn in enumerate(methods[:8]):
    if 0x400000<=fn<0x6e0000:(OUT/(f'rtti_{vtable:08x}_{n}_{fn:08x}.txt')).write_text(dis(fn,0x700))
 rtti.append({'class':row['text'],'descriptor':hex(descriptor),'locators':locators})
(OUT/'battle_rtti.json').write_text(json.dumps(rtti,indent=2))
for name,va,size in [
 ('enemy_component',0x50e050,0x220),('enemy_action_component',0x50d700,0x860),
 ('battle_actor',0x50ee00,0x1b00),('npc_menu_dispatch',0x52cc40,0x580),
 ('world_target',0x505900,0x1100),('command_queue',0x4f5700,0x820)
 ]:(OUT/(name+'.txt')).write_text(dis(va,size))
