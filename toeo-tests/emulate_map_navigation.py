"""Verify all preserved navigation runs with the original 415090 consumer."""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX,UC_X86_REG_EIP
from emulate_character_list import CharacterFixture
from world_map_navigation import NAV_RLE,NAV_WIDTH,NAV_HEIGHT

def run(binary):
    f=CharacterFixture(binary);meta,table,stream=0x10b0000,0x10c0000,0x11d0000
    n=NAV_WIDTH*NAV_HEIGHT
    f.uc.mem_write(table,struct.pack('<III',1,0,0)*n)
    for off,value in ((4,table),(8,table+n*12),(0x14,0x1144000),(0xa4,NAV_WIDTH),(0xa8,NAV_HEIGHT),(0xd8,NAV_WIDTH*2),(0xdc,NAV_HEIGHT)):
        f.write32(meta+off,value)
    f.uc.mem_write(stream,NAV_RLE+bytes(4))
    sp=0x20fe000;f.uc.mem_write(sp,struct.pack('<4I',f.stop,stream,n,0))
    f.uc.reg_write(UC_X86_REG_ESP,sp);f.uc.reg_write(UC_X86_REG_ECX,meta)
    f.uc.emu_start(0x415090,f.stop,count=100000000)
    values=list(memoryview(bytes(f.uc.mem_read(table,n*12))).cast('I'))[::3]
    expected=[]
    for bit,count in zip(NAV_RLE[::2],NAV_RLE[1::2]):expected.extend([0 if bit else 1]*count)
    assert len(expected)==n
    mismatches=[(i,v&3,expected[i]) for i,v in enumerate(values) if v&3!=expected[i]]
    assert not mismatches,{'pc':hex(f.uc.reg_read(UC_X86_REG_EIP)),'mismatch_count':len(mismatches),'first':mismatches[:5]}
    cells={}
    for grid in [(6,4),(10,8),(19,7),(13,21),(21,25)]:
        f.invoke(0x414860,grid,this=meta)
        value=f.uc.reg_read(UC_X86_REG_EAX);cells[str(grid)]={'native_flags':value,'blocked':bool(value&3)}
    assert not any(cells[str(g)]['blocked'] for g in [(6,4),(10,8),(19,7)])
    assert all(cells[str(g)]['blocked'] for g in [(13,21),(21,25)])
    return {'passed':True,'original_consumer':'415090','grid_cells_verified':n,
        'walkable_cells':expected.count(0),'samples':cells,
        'limitations':['Native metadata is a fixture initialized with blocked cells','Real Windows map movement requires separate evidence']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    result=run(a.binary);Path(a.out).write_text(json.dumps(result,indent=2))
    print('ORIGINAL_MAP_NAVIGATION_RLE_PASS',result['grid_cells_verified'])
