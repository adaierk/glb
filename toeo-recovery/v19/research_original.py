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

subprocess.run(['7z','x','-y','-o'+str(raw),str(pack),'NewComponent1/resource/se000.cpd','NewComponent1/resource/se000.atd'],check=True,stdout=subprocess.DEVNULL)
(OUT/'original_symbol_enemy_cpd.json').write_text(json.dumps(cpd_decode('se000.cpd'),indent=2))
for name,va,size in [
 ('battle_group_pool_init',0x514360,0x900),('battle_background_setup',0x44f2a0,0xb00),
 ('battle_native_entry_tick',0x433dd0,0x850),('native_selection_click',0x505200,0x730),
 ('battle_arena_init',0x49d100,0x1f0),('battle_group_resource',0x49bad0,0x1b0)
 ]:(OUT/(name+'.txt')).write_text(dis(va,size))
# Follow original NPC/actor command dispatcher for native action1 vs2.
(OUT/'npc_menu_action_mask.txt').write_text(dis(0x5b9a90,0x700))
(OUT/'native_action66.txt').write_text(dis(0x4f7120,0x110))

for name,va,size in [
 ('battle_background_id',0x44f0f0,0x160),('battle_actor_initialize',0x511dd0,0x1300),
 ('native_menu_execute',0x5b9110,0xb00),('world_mode_tick',0x43eb50,0x650)
 ]:(OUT/(name+'.txt')).write_text(dis(va,size))
(OUT/'native_menu_table.json').write_text(json.dumps([list(struct.unpack('<4I',pe.get_data(0x7b3470-base+16*n,16))) for n in range(16)],indent=2))
files=subprocess.check_output(['7z','l','-slt',str(pack)],text=True)
(OUT/'battle_asset_paths.json').write_text(json.dumps([line[7:] for line in files.splitlines() if line.startswith('Path = ') and re.search(r'(^|/)(battle|b[0-9_])|\.bmd$|\.btt$',line[7:],re.I)],indent=2))

(OUT/'battle_background_loader.txt').write_text(dis(0x45e280,0x1d00))
(OUT/'battle_background_strings.json').write_text(json.dumps([{'address':hex(i),'bytes':pe.get_data(i-base,100).split(bytes(1),1)[0].decode('cp932','replace')} for i in (0x6e7f94,0x6e7f7c,0x6e96a0,0x6e9690)],indent=2))
(OUT/'battle_data_paths.json').write_text(json.dumps([line[7:] for line in files.splitlines() if line.startswith('Path = ') and re.search(r'(?i)(bg|btl|bmf|battle|/bmap|/bfield)|\.(bmi|bmt|bmd|bpd|bpi|tmd|tmi)$',line[7:])],indent=2))

(OUT/'whole_actor_model_bank_lookup.txt').write_text(dis(0x4d9b90,0x270))
(OUT/'appearance_humanoid_predicate.txt').write_text(dis(0x405e70,0x20))
(OUT/'battle_background_format.json').write_text(json.dumps([{'address':hex(i),'text':pe.get_data(i-base,90).split(bytes(1),1)[0].decode('cp932','replace')} for i in (0x6e820c,0x6e8200)],indent=2))

(OUT/'model_table_filenames.json').write_text(json.dumps([{'address':hex(i),'text':pe.get_data(i-base,120).split(bytes(1),1)[0].decode('cp932','replace')} for i in (0x6ecec8,0x6eceb4,0x6ecea0,0x6ece8c,0x6ece78)],indent=2))
(OUT/'nntable_loader.txt').write_text(dis(0x41b480,0x780))
(OUT/'nntable_paths.json').write_text(json.dumps([line[7:] for line in files.splitlines() if line.startswith('Path = ') and re.search(r'(?i)(nnt|\.nnt|\.nn)',line[7:])],indent=2))

(OUT/'model_id_map_constructor.txt').write_text(dis(0x41b050,0x3a0))

for name,va,size in [('battle_model_resource',0x50fcf0,0x5e0),('battle_field_model_load',0x4ff070,0x360),('battle_actor_model_start',0x5109a0,0x640),('model_id_map_accessor',0x41a800,0x50)]:
 (OUT/(name+'.txt')).write_text(dis(va,size))

for name,va,size in [('world_actor_pool_construct',0x509db0,0x420),('world_actor_initialize',0x502350,0x1000),('world_model_load_calls',0x4fe3f0,0x660)]:
 (OUT/(name+'.txt')).write_text(dis(va,size))
refs_model=[]
for sec in pe.sections:
 if not sec.Characteristics&0x20000000:continue
 body=sec.get_data();start=base+sec.VirtualAddress
 for m in re.finditer(b'\xe8',body):
  at=m.start()
  if at+5<=len(body) and (start+at+5+struct.unpack_from('<i',body,at+1)[0])&0xffffffff==0x501470:
   refs_model.append(hex(start+at))
   (OUT/f'model_call_{start+at:x}.txt').write_text(dis(start+max(0,at-0x100),0x220))
(OUT/'world_model_calls.json').write_text(json.dumps(refs_model,indent=2))
