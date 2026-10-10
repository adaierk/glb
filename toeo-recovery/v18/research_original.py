"""Read original client bytes and assets for the next equipment stage."""
import hashlib,json,re,struct,subprocess
from pathlib import Path
import pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
ROOT=Path.cwd();OUT=ROOT/'toeo-recovery/v18/research';OUT.mkdir(parents=True,exist_ok=True)
pack=Path(__import__('os').environ['RUNNER_TEMP'])/'TOEO_ORIGINAL/client_pack.7z'
raw=Path(__import__('os').environ['RUNNER_TEMP'])/'TOEO_V18_RAW'
subprocess.run(['7z','x','-y','-o'+str(raw),str(pack),'DefaultComponent/ToEO_CL.dat','NewComponent1/resource/*','NewComponent1/ui/*'],check=True,stdout=subprocess.DEVNULL)
binary=raw/'DefaultComponent/ToEO_CL.dat';data=binary.read_bytes()
assert hashlib.sha256(data).hexdigest()=='635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'
pe=pefile.PE(data=data);base=pe.OPTIONAL_HEADER.ImageBase;cs=Cs(CS_ARCH_X86,CS_MODE_32);cs.skipdata=True
ranges={
 'world_model_selection':(0x501300,0x650),
 'model_layer_loader':(0x518ed0,0x900),
 'inventory_definition_records':(0x51f030,0x900),
 'item_constructor_copy':(0x51c800,0x1000),
 'equipment_move_receipt':(0x4f9720,0x750),
 'world_b2_callback':(0x52ca9b,0x100),
 'world_attribute_records':(0x526610,0x2a00),
 'visual_record_decoder':(0x51d5c0,0x140),
 'actor_visual_components':(0x4fed50,0x340),
 'model_layer_setter':(0x518280,0x3c0),
 'actor_model_refresh':(0x500280,0x350),
 'equipment_visual_preview':(0x550e00,0x1000),
 'model_class_lookup':(0x4d81f0,0x450),
 'model_body_change_lookup':(0x4d9b90,0x200),
 'initial_player_record':(0x43f300,0x400),
}
for name,(va,length) in ranges.items():
 code=pe.get_data(va-base,length)
 text='\n'.join(f'{i.address:08x}  {i.mnemonic:8s} {i.op_str}' for i in cs.disasm(code,va))
 (OUT/(name+'.txt')).write_text(text)
targets={0x518ed0:'model_layer_loader',0x51f030:'inventory_records',0x51ee00:'gear_insert',0x501470:'world_model_initial_load',0x518280:'model_set_layer',0x517f70:'model_set_resource'}
refs=[]
for section in pe.sections:
 if not section.Characteristics&0x20000000:continue
 body=section.get_data();start=base+section.VirtualAddress
 for i,b in enumerate(body[:-4]):
  if b!=0xe8:continue
  target=(start+i+5+struct.unpack_from('<i',body,i+1)[0])&0xffffffff
  if target in targets:
   refs.append({'address':hex(start+i),'target':hex(target),'symbol':targets[target]})
   left=max(0,i-60);snippet='\n'.join(f'{x.address:08x}  {x.mnemonic:8s} {x.op_str}' for x in cs.disasm(body[left:i+35],start+left))
   (OUT/f'call_{start+i:08x}_{targets[target]}.txt').write_text(snippet)
(OUT/'call_references.json').write_text(json.dumps(refs,indent=2))
resources=raw/'NewComponent1/resource'
entries=[]
for p in sorted(resources.rglob('*')):
 if p.is_file():
  entries.append({'path':str(p.relative_to(resources)),'bytes':p.stat().st_size})
(OUT/'resource_inventory.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2))
texts=[]
for m in re.finditer(rb'[\x20-\x7e]{5,}',data):
 s=m.group().decode()
 if any(x in s.lower() for x in ('armor','weapon','body','parts','equip','.smd','.smc','.skn','.mdf','.bmp','.tga')):
  texts.append({'offset':m.start(),'text':s[:240]})
(OUT/'asset_strings.json').write_text(json.dumps(texts,indent=2))
print(json.dumps({'original_exe_sha256':hashlib.sha256(data).hexdigest(),'ranges':len(ranges),'call_references':len(refs),'resources':len(entries),'asset_strings':len(texts)}))

import sys
sys.path.insert(0,str(ROOT/'toeo-tests'))
from decode_client_tables import decode_table
for name in ('cid0.idt','cid1.idt','cty2rs.nnt'):
 meta,rows=decode_table(resources/name)
 (OUT/(name+'.json')).write_text(json.dumps({'metadata':meta,'rows':rows},ensure_ascii=False,indent=2))
cpds=[]
for name in ('pc1a_m.cpd','pc1a_l.cpd','pc1b_m.cpd','pc1b_l.cpd','pc_hat.cpd','pc_weapon.cpd'):
 body=(resources/name).read_bytes()
 cpds.append({'file':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'header_hex':body[:192].hex(),'first_words':list(struct.unpack_from('<'+'I'*48,body))})
(OUT/'pc_model_headers.json').write_text(json.dumps(cpds,indent=2))
# Locate operands touching measured visual fields without assuming function names.
field_refs=[]
for section in pe.sections:
 if not section.Characteristics&0x20000000:continue
 body=section.get_data();start=base+section.VirtualAddress
 for displacement in (0x1a8,0x1ac,0xb0):
  needle=struct.pack('<I',displacement);pos=0
  while True:
   pos=body.find(needle,pos)
   if pos<0:break
   for back in (2,3,4,5,6):
    at=pos-back
    if at<0:continue
    ins=list(cs.disasm(body[at:pos+9],start+at,count=1))
    if ins and ins[0].address+ins[0].size>=start+pos+4 and f'+ 0x{displacement:x}]' in ins[0].op_str:
     row={'address':hex(ins[0].address),'displacement':hex(displacement),'instruction':ins[0].mnemonic+' '+ins[0].op_str}
     if row not in field_refs:field_refs.append(row)
   pos+=1
(OUT/'visual_field_operands.json').write_text(json.dumps(field_refs,indent=2))
for row in field_refs:
 va=int(row['address'],16)
 if (0x4ff000<=va<0x502000 or 0x526000<=va<0x528000):
  left=va-70
  text='\n'.join(f'{i.address:08x}  {i.mnemonic:8s} {i.op_str}' for i in cs.disasm(pe.get_data(left-base,180),left))
  (OUT/f'field_{va:08x}.txt').write_text(text)

switch=[]
indices=pe.get_data(0x528f20-base,0x9d)
for index,handler_index in enumerate(indices):
 handler=struct.unpack('<I',pe.get_data(0x528e50-base+handler_index*4,4))[0]
 code=pe.get_data(handler-base,160)
 switch.append({'record':hex(index+0x49),'handler':hex(handler),'instructions':[i.mnemonic+' '+i.op_str for i in cs.disasm(code,handler)][:26]})
(OUT/'world_attribute_switch.json').write_text(json.dumps(switch,indent=2))
visual_switch=[{'record':hex(i+0x36),'handler':hex(struct.unpack('<I',pe.get_data(0x51f594-base+i*4,4))[0])} for i in range(13)]
(OUT/'inventory_record_switch.json').write_text(json.dumps(visual_switch,indent=2))
