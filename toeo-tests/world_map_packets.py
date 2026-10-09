"""Local world initialization candidate from original 43F090 record readers."""
import struct
from account_packets import message
from native_map_geometry import point_to_grid

# Resource names and original minimap %x formatter use hexadecimal map IDs.
LOCAL_MAP_ID=0x1110101

def record(kind,size):
    if size%4:raise ValueError('Native record size must be DWORD aligned')
    b=bytearray(size);struct.pack_into('<HH',b,0,kind,size//4);return b

def map_record(map_id=LOCAL_MAP_ID):
    b=record(0x20,0xe4)
    struct.pack_into('<II',b,4,map_id,1)
    label='Local World'.encode('utf-16le');b[0x24:0x24+len(label)]=label
    for offset,suffix in [(0x64,'mpd'),(0x84,'mpi'),(0xa4,'bnd')]:
        path=f'map/{map_id:07x}.{suffix}'.encode('ascii')
        if len(path)>=32:raise ValueError('Native map path exceeds fixed record field')
        b[offset:offset+len(path)]=path
    return bytes(b)

def world_clock_record():
    b=record(0xbf,20)
    # This record feeds 4F5280's clock/weather state. Zero disables timed effects.
    return bytes(b)

def player_record(identity,name,selector_fields,position=(224.,80.),map_id=LOCAL_MAP_ID):
    if len(selector_fields)!=248:raise ValueError('Expected preserved selector fields')
    b=record(0x21,0x284)
    struct.pack_into('<II',b,4,*identity)
    struct.pack_into('<II',b,0xc,*identity)
    # 43F382 -> 503995/50399B copies these DWORDs to actor+74/+78:
    # they are status masks, not pixel coordinates. Position comes from grid.
    struct.pack_into('<II',b,0x14,0,0)
    struct.pack_into('<I',b,0x1c,1)
    # Native 43F3E9 -> 503AC7 assigns the current player map;
    # 43F3FA -> 4FF9C0 resolves grid cells back to their pixel centers.
    struct.pack_into('<I',b,0x24,map_id)
    struct.pack_into('<hh',b,0x28,*point_to_grid(position))
    raw=name.encode('utf-16le')
    if len(raw)>62:raise ValueError('Player name exceeds original fixed field')
    b[0x38:0x38+len(raw)]=raw
    # Original 43f38e copies this 24-byte appearance object; 501584/50162e
    # then uses exactly the selector's model and appearance parameters.
    b[0x7c:0x94]=selector_fields[0x30:0x48]
    # World attributes are a separate 456-byte structure (405e90), not a
    # selector record. Preserve its two measured constructor defaults.
    struct.pack_into('<I',b,0x94,1)
    struct.pack_into('<I',b,0x94+0xdc,1)
    # Original 4FFDxx/4FFExx readers: current and maximum HP/TP.
    struct.pack_into('<II',b,0x94+8,100,30)
    struct.pack_into('<II',b,0x94+0xa8,100,30)
    b[0x30:0x33]=bytes((1,0,0))
    return bytes(b)

def world_initialization_reply(identity,name,selector_fields,request_id,map_id=LOCAL_MAP_ID):
    b=bytearray(40)
    records=map_record(map_id)+world_clock_record()+player_record(identity,name,selector_fields,map_id=map_id)+bytes(4)
    size=len(b)+len(records)
    b[:9]=message(0x34,bytes(size-9),request_id)[:9]
    struct.pack_into('<I',b,12,size)
    struct.pack_into('<III',b,20,*identity,1)
    return bytes(b)+records

def world_map_ready_reply(request_id,map_id=LOCAL_MAP_ID):
    # Original world 3A consumer 52a200 requires a 40-byte fixed header;
    # length 40 means no optional A8/A9/AA records follow. 441731 reads
    # signed status at +16, and 52a260 looks up the loaded map at +36.
    b=bytearray(message(0x3a,bytes(31),request_id))
    struct.pack_into('<I',b,12,len(b))
    # 52A3A8 reads +18 and calls 4FE6C0 to set actor+144. 505BAD
    # requires this permission before requesting a path from ground clicks.
    b[18]=1
    struct.pack_into('<I',b,36,map_id)
    return bytes(b)
