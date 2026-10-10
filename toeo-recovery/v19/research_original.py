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

for name,va,size in [
 ('actor_model_dispatch',0x501470,0xb00),('battle_enter_modes',0x4ecb10,0x750),
 ('world_command_more',0x522c20,0x750),('battle_record_59',0x529840,0x1200),
 ('battle_record_group',0x49d2f0,0x900),('encounter_request',0x430000,0xc00),
 ('battle_status_start',0x49e1c0,0x600),('world_click_target',0x505c90,0x750)
 ]:(OUT/(name+'.txt')).write_text(dis(va,size))
code_refs=[]
more_targets={0x4ece10:'battle_enter_modes',0x431d10:'battle_task_ctor',0x529840:'battle_actor_record',0x49d2f0:'battle_group',0x430e50:'battle_init'}
for sec in pe.sections:
 if not sec.Characteristics&0x20000000:continue
 body=sec.get_data();start=base+sec.VirtualAddress
 for m in re.finditer(b'\xe8',body):
  at=m.start()
  if at+5>len(body):continue
  dest=(start+at+5+struct.unpack_from('<i',body,at+1)[0])&0xffffffff
  if dest in more_targets:code_refs.append({'address':hex(start+at),'target':hex(dest),'kind':more_targets[dest]})
 builders=[];last=0
 for i in cs.disasm(body,start):
  if i.mnemonic=='push' and i.op_str=='ebp':last=i.address
  if i.mnemonic=='mov' and i.op_str.startswith('word ptr [ebp') and ',' in i.op_str:
   dst,value=i.op_str.rsplit(',',1)
   try:op=int(value.strip(),0)
   except ValueError:continue
   if 0x90<=op<=0xb2:
    builders.append({'address':hex(i.address),'value':hex(op),'possible_function':hex(last),'instruction':i.mnemonic+' '+i.op_str})
    if 0x9c<=op<=0xad:(OUT/(f'builder_{op:x}_{last:x}.txt')).write_text(dis(last,0x900))
(OUT/'combat_refs_more.json').write_text(json.dumps(code_refs,indent=2))
(OUT/'combat_builders.json').write_text(json.dumps(builders,indent=2))

for name,va,size in [
 ('world_action_request',0x4f9540,0x720),('battle_group_validate',0x49bc70,0xe00),
 ('battle_state_constructor',0x50f980,0x800),('battle_actor_construct',0x515650,0x900),
 ('battle_world_task',0x43e900,0x1800),('original_crs_banks',0x4d9e00,0xd00)
 ]:(OUT/(name+'.txt')).write_text(dis(va,size))
targets4={0x4f9540:'world_action_request',0x522fd0:'battle_a8',0x5231b0:'battle_9f',0x49bad0:'battle_group_activate'}
refs4=[]
for sec in pe.sections:
 if not sec.Characteristics&0x20000000:continue
 body=sec.get_data();start=base+sec.VirtualAddress
 for m in re.finditer(b'\xe8',body):
  at=m.start()
  if at+5>len(body):continue
  dest=(start+at+5+struct.unpack_from('<i',body,at+1)[0])&0xffffffff
  if dest in targets4:
   ref=start+at;refs4.append({'address':hex(ref),'target':hex(dest),'kind':targets4[dest]})
   left=max(0,at-0x130)
   (OUT/f'combat_ref_{ref:x}.txt').write_text(dis(start+left,0x280))
(OUT/'combat_refs4.json').write_text(json.dumps(refs4,indent=2))
sys.path.insert(0,str(ROOT/'toeo-tests'))
from decode_client_tables import decrypt_blocks
def cpd_decode(name):
 b=(raw/'NewComponent1/resource'/name).read_bytes()
 count,offset,rows,start=struct.unpack_from('<IIII',b,12);plain=bytearray(b);strings={}
 for n in range(count):
  size=u=struct.unpack_from('<I',b,offset)[0];offset+=4
  value=decrypt_blocks(b[offset:offset+size],b'cpd text');plain[offset:offset+size]=value
  strings[offset]=value.split(bytes(1),1)[0].decode('cp932');offset+=size
 return {'file':name,'sha256':hashlib.sha256(b).hexdigest(),'rows':[{'words':list(struct.unpack_from('<14I',plain,start+n*56)),'labels':[strings.get(v) for v in struct.unpack_from('<14I',plain,start+n*56)]} for n in range(rows)]}
(OUT/'original_enemy_cpd.json').write_text(json.dumps([cpd_decode('e000.cpd'),cpd_decode('e001.cpd')],indent=2))
