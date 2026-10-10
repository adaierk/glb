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
pe=pefile.PE(data=data);base=pe.OPTIONAL_HEADER.ImageBase;cs=Cs(CS_ARCH_X86,CS_MODE_32)
ranges={
 'world_model_selection':(0x501300,0x650),
 'model_layer_loader':(0x518ed0,0x900),
 'inventory_definition_records':(0x51f030,0x900),
 'item_constructor_copy':(0x51c800,0x1000),
 'equipment_move_receipt':(0x4f9720,0x750),
 'world_b2_callback':(0x52ca70,0x170),
 'initial_player_record':(0x43f300,0x400),
}
for name,(va,length) in ranges.items():
 code=pe.get_data(va-base,length)
 text='\n'.join(f'{i.address:08x}  {i.mnemonic:8s} {i.op_str}' for i in cs.disasm(code,va))
 (OUT/(name+'.txt')).write_text(text)
targets={0x518ed0:'model_layer_loader',0x51f030:'inventory_records',0x51ee00:'gear_insert',0x501410:'world_model_refresh_candidate'}
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
