"""Compare original selector and world-actor model/loader field projection."""
import argparse,json
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EAX
from emulate_character_fields import FieldFixture
from character_store import native_character_fields
from world_map_packets import player_record

def run(binary):
    cases=[]
    for parameters in [(1,1,0,0,0,0,0,0,0,1),(5,2,1,2,3,4,5,6,7,1)]:
        f=FieldFixture(binary)
        f.request_create('Archive',parameters)
        fields=native_character_fields((1,1),'Archive',parameters)
        f.uc.mem_write(f.native,fields)
        f.write32(f.native+0x114,0) # No pre-existing resource to destroy in this fixture.
        f.slice(0x434bc0,None,f.native,this=f.native)
        selector_args=f.loader_args
        assert selector_args is not None
        actor,appearance,profile=0x104b000,0x104c000,0x104d000
        rec=player_record((1,1),'Archive',fields)
        f.uc.mem_write(appearance,rec[0x7c:0x94])
        f.uc.mem_write(profile,rec[0x94:0x25c])
        f.write32(actor+0x110,appearance);f.write32(actor+0x114,profile)
        f.write32(actor+0x70,1);f.write32(actor+0x158,0x104e000)
        f.slice(0x501564,0x5015cb,actor)
        model=f.uc.reg_read(UC_X86_REG_EAX)
        f.write32(0x20fe000-0x14,model)
        f.slice(0x50162e,None,actor)
        assert f.loader_args==selector_args and model!=0 and not f.assertions
        cases.append(dict(parameters=parameters,model=model,selector_args=selector_args,world_args=f.loader_args))
    return dict(passed=True,cases=cases,limitations=['Original model lookup and argument loads; resource rendering checked in Windows separately'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();Path(a.out).write_text(json.dumps(run(a.binary),indent=2))
    print('ORIGINAL_WORLD_APPEARANCE_PROJECTION_PASS')
