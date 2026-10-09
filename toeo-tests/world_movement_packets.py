"""Original 522580 movement request and 52AE8A success acknowledgment."""
import struct
from account_packets import message
from native_map_geometry import point_to_grid
from world_map_navigation import GRID_WIDTH,GRID_HEIGHT

def parse_move_request(packet,profile=None):
    if len(packet)!=68 or struct.unpack_from('<HH',packet,1)!=(0x42,68):
        raise ValueError('Expected original 68-byte movement request')
    start=struct.unpack_from('<ff',packet,52)
    source=point_to_grid(start)
    target=struct.unpack_from('<hh',packet,60)
    mode=packet[65]
    if mode not in (1,2,3):raise ValueError('Unsupported native movement mode')
    for grid in (source,target):
        valid=profile.in_bounds(grid) if profile is not None else (0<=grid[0]<GRID_WIDTH and 0<=grid[1]<GRID_HEIGHT and (grid[0]-grid[1])%2==0)
        if not valid:raise ValueError('Movement outside the selected original map grid')
    return {'request_id':struct.unpack_from('<I',packet,5)[0],
        'sequence':struct.unpack_from('<I',packet,12)[0],
        'identity':struct.unpack_from('<II',packet,28),
        'map_id':struct.unpack_from('<I',packet,36)[0],
        'source':source,'target':target,'mode':mode,
        'speed':1.5 if mode in (2,3) else 1.0,'start_point':start}

def move_reply(move):
    b=bytearray(message(0x43,bytes(39),move['request_id']))
    struct.pack_into('<III',b,12,move['sequence'],*move['identity'])
    struct.pack_into('<I',b,24,move['map_id'])
    struct.pack_into('<hhhh',b,28,*move['source'],*move['target'])
    struct.pack_into('<bb',b,36,-1,move['mode'])
    struct.pack_into('<f',b,44,move['speed'])
    return bytes(b)

def move_rejection_reply(move,authoritative_grid):
    """Native -93 branch (52B0CE) stops prediction and restores source grid.

The original semantic name of this status is unknown. Its stop/restore behavior
is executed by emulate_movement_rejection.py; no native state is injected.
"""
    b=bytearray(move_reply(move))
    struct.pack_into('<h',b,10,-93)
    struct.pack_into('<hh',b,28,*authoritative_grid)
    return bytes(b)
