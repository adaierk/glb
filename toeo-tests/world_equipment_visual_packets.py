"""Original 43/44/45 visual component records; explicit local gear mapping."""
import struct
from account_packets import message
from world_map_packets import record
from world_equipment_definitions import equipment_definition

def equipment_visual_records(snapshot):
    header=record(0x43,8)
    tail=bytearray(header)
    for item in snapshot.get('equipment',[]):
        definition=equipment_definition(item)
        if definition is None or not definition.get('visual_resource'):continue
        r=record(0x44,36)
        struct.pack_into('<I',r,4,definition['slot'])
        struct.pack_into('<IIIIIII',r,8,*item['identity'],definition.get('visual_source_bank',0),definition['visual_resource'],definition['visual_layer'])
        tail.extend(r)
    tail.extend(record(0x45,4))
    return bytes(tail)

def equipment_visual_notice(identity,map_id,snapshot):
    tail=equipment_visual_records(snapshot)+bytes(4)
    b=bytearray(message(0x6c,bytes(35+len(tail)),0xffffffff))
    # 52BA8D lookup: map +10, role +14/+18. +1C is the separate
    # full-body override (zero), +20/+24/+28 preserve idle fields.
    struct.pack_into('<IIIIIIII',b,12,len(b),map_id,*identity,0,0,0,0)
    b[44:]=tail
    return bytes(b)
