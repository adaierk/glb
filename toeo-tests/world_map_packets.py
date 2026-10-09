"""Local world initialization candidate from original 43F090 record readers."""
import struct
from account_packets import message

def record(kind,size):
    if size%4:raise ValueError('Native record size must be DWORD aligned')
    b=bytearray(size);struct.pack_into('<HH',b,0,kind,size//4);return b

def map_record(map_id=1110101):
    b=record(0x20,0xe4)
    struct.pack_into('<II',b,4,map_id,1)
    label='Local World'.encode('utf-16le');b[0x24:0x24+len(label)]=label
    for offset,suffix in [(0x64,'mpd'),(0x84,'mpi'),(0xa4,'bnd')]:
        path=f'map/{map_id}.{suffix}'.encode('ascii')
        if len(path)>=32:raise ValueError('Native map path exceeds fixed record field')
        b[offset:offset+len(path)]=path
    return bytes(b)

def world_clock_record():
    b=record(0xbf,20)
    # This record feeds 4F5280's clock/weather state. Zero disables timed effects.
    return bytes(b)

def player_record(identity,name,selector_fields,position=(3200.,3200.)):
    if len(selector_fields)!=248:raise ValueError('Expected preserved selector fields')
    b=record(0x21,0x284)
    struct.pack_into('<II',b,4,*identity)
    struct.pack_into('<II',b,0xc,*identity)
    struct.pack_into('<ff',b,0x14,*position)
    struct.pack_into('<I',b,0x1c,1)
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
    b[0x30:0x33]=bytes((1,0,0))
    return bytes(b)

def world_initialization_reply(identity,name,selector_fields,request_id,map_id=1110101):
    b=bytearray(40)
    records=map_record(map_id)+world_clock_record()+player_record(identity,name,selector_fields)+bytes(4)
    size=len(b)+len(records)
    b[:9]=message(0x34,bytes(size-9),request_id)[:9]
    struct.pack_into('<I',b,12,size)
    struct.pack_into('<III',b,20,*identity,1)
    return bytes(b)+records

def world_map_ready_reply(request_id,map_id=1110101):
    # Original world 3A consumer 52a200 requires a 40-byte fixed header;
    # length 40 means no optional A8/A9/AA records follow. 441731 reads
    # signed status at +16, and 52a260 looks up the loaded map at +36.
    b=bytearray(message(0x3a,bytes(31),request_id))
    struct.pack_into('<I',b,12,len(b))
    struct.pack_into('<I',b,36,map_id)
    return bytes(b)
