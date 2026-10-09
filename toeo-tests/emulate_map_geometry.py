"""Compare local diamond-grid conversion with actual original x86 routines."""
import argparse,json,random,struct
from pathlib import Path
from emulate_character_list import CharacterFixture
from native_map_geometry import point_to_grid,grid_to_point

def run(binary):
    f=CharacterFixture(binary);meta,pos,out=0x10b0000,0x10b0400,0x10b0500
    for offset,value in [(0xac,64),(0xb0,32),(0xcc,32),(0xd0,16)]:f.write32(meta+offset,value)
    f.uc.mem_write(meta+0xc8,struct.pack('<f',.5))
    points=[(224,80),(416,144),(0,0),(32,16),(64,32),(360,148),(620,128)]
    rng=random.Random(49)
    points += [(rng.randrange(1,4000),rng.randrange(1,3000)) for _ in range(180)]
    for position in points:
        f.uc.mem_write(pos,struct.pack('<ff',*position))
        f.invoke(0x413bd0,(out,pos),this=meta)
        grid=struct.unpack('<ii',f.uc.mem_read(out,8))
        assert grid==point_to_grid(position),(position,grid,point_to_grid(position))
        f.uc.mem_write(pos,struct.pack('<ii',*grid))
        f.invoke(0x413d10,(out,pos),this=meta)
        actual=struct.unpack('<ff',f.uc.mem_read(out,8))
        assert actual==grid_to_point(grid),(grid,actual,grid_to_point(grid))
    return dict(passed=True,original_routines=['413BD0','413D10'],verified_points=len(points),
                scope='64 x 32 native map; geometry only, not full path collision')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    result=run(a.binary);Path(a.out).write_text(json.dumps(result,indent=2))
    print('ORIGINAL_MAP_GRID_CONVERSIONS_PASS',result['verified_points'])
