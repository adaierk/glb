"""v21 read-only original battle initialization and input investigation."""
import hashlib,json,os,re,struct,subprocess
from pathlib import Path
import pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
ROOT=Path.cwd();OUT=ROOT/'toeo-recovery/v21/research';OUT.mkdir(parents=True,exist_ok=True)
raw=Path(os.environ['RUNNER_TEMP'])/'TOEO_V21_RAW'
pack=Path(os.environ['RUNNER_TEMP'])/'TOEO_ORIGINAL/client_pack.7z'
subprocess.run(['7z','x','-y','-o'+str(raw),str(pack),'DefaultComponent/ToEO_CL.dat'],check=True,stdout=subprocess.DEVNULL)
data=(raw/'DefaultComponent/ToEO_CL.dat').read_bytes()
assert hashlib.sha256(data).hexdigest()=='635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'
pe=pefile.PE(data=data);base=pe.OPTIONAL_HEADER.ImageBase
cs=Cs(CS_ARCH_X86,CS_MODE_32);cs.skipdata=True
def dis(va,size):
 return '\n'.join(f'{i.address:08x}  {i.mnemonic:8s} {i.op_str}' for i in cs.disasm(pe.get_data(va-base,size),va))
ranges={
'battle_control_a1':(0x52c1a4,0x154),
'battle_abilities_a3':(0x52c2f8,0x1fd),
'battle_state_a5':(0x52c4f5,0x610),
'battle_actor_input':(0x513000,0xaa0),
'battle_actor_action':(0x50ee00,0xba0),
'battle_actor_ability_insert':(0x5112c0,0x220),
'ability_resource_lookup':(0x46eaf0,0x340),
'battle_request_builders':(0x522fd0,0x790),
'battle_actor_initial_state':(0x50f980,0x190),
'battle_main_tick':(0x433dd0,0xa00),
'battle_input_manager':(0x4eec10,0xe50),
'battle_ability_sources':(0x4340e0,0x380),
'field_group_assignment':(0x4ffcd0,0x340),
'battle_pool_start_aa':(0x5146a0,0x430),
'battle_pick_bounds':(0x515900,0x500),
'battle_action_a9':(0x49c510,0x7a0),
'battle_target_builder':(0x5228a0,0x260),
'world_target_reply':(0x52b6ae,0xd0),
'battle_collision_load':(0x50fcf0,0x300),
'battle_position_action':(0x510090,0x170),
'battle_action_classify':(0x48d860,0x100),
'battle_results_main':(0x433dd0,0xa00),
'battle_start_input_gate':(0x512ff0,0x100),
'battle_target_native':(0x50f500,0x170),
'field_target_native':(0x4feb90,0xa0),
'action_actor_reference':(0x4916d0,0x390),
'action_classify_full':(0x48d860,0x450),
'command_script_factory':(0x4707a0,0x790)
}
for name,(va,size) in ranges.items():(OUT/(name+'.txt')).write_text(dis(va,size))
targets={0x515710:'pool_tick',0x515870:'pool_walk',0x519140:'model_orientation',0x518ed0:'model_ctor'}
refs=[]
for sec in pe.sections:
 if not sec.Characteristics&0x20000000:continue
 body=sec.get_data();start=base+sec.VirtualAddress
 for m in re.finditer(b'\xe8',body):
  at=m.start()
  if at+5>len(body):continue
  dst=(start+at+5+struct.unpack_from('<i',body,at+1)[0])&0xffffffff
  if dst in targets:
   ref=start+at;refs.append({'va':hex(ref),'target':hex(dst),'kind':targets[dst]})
   if 0x50ee00<=ref<0x519000:(OUT/f'render_ref_{ref:x}.txt').write_text(dis(ref-0x90,0x180))
(OUT/'render_refs.json').write_text(json.dumps(refs,indent=2))
(OUT/'original_binary.json').write_text(json.dumps({'sha256':hashlib.sha256(data).hexdigest(),'ranges':ranges},indent=2))
print('V21_ORIGINAL_INPUT_RESEARCH_PASS',len(refs))

subprocess.run(['7z','x','-y','-o'+str(raw),str(pack),'NewComponent1/resource/pc1a.atd','NewComponent1/resource/e000.atd'],check=True,stdout=subprocess.DEVNULL)
(OUT/'battle_animation_asset_headers.json').write_text(json.dumps([{'file':n,'sha256':hashlib.sha256((raw/'NewComponent1/resource'/n).read_bytes()).hexdigest(),'header_hex':(raw/'NewComponent1/resource'/n).read_bytes()[:512].hex()} for n in ('pc1a.atd','e000.atd')],indent=2))

animation_assets=[]
for name in ('pc1a.atd','e000.atd'):
 b=(raw/'NewComponent1/resource'/name).read_bytes();count,start=struct.unpack_from('<II',b,20)
 rows=[]
 for n in range(count):
  words=struct.unpack_from('<7I',b,start+n*28);num,off=words[5:7]
  assert num<=8 and off+16*num<=len(b)
  rows.append({'row':n,'words':list(words),'serialized_direction_labels':[chr(b[off+16*i]) for i in range(num)],'direction_entries_hex':[b[off+16*i:off+16*(i+1)].hex() for i in range(num)]})
 animation_assets.append({'file':name,'sha256':hashlib.sha256(b).hexdigest(),'rows':rows})
(OUT/'original_battle_animation_directions.json').write_text(json.dumps(animation_assets,indent=2))
