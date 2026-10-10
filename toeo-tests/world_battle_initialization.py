"""Original A1/A2 and A3/A4 battle initialization, with bounded local fixtures."""
import struct
from account_packets import message
from world_combat_packets import BATTLE_GROUP

def battle_control_notice(identity,map_id,request_id,control_flags=0):
    return message(0xa1,bytes(3)+struct.pack('<6I',*identity,map_id,*BATTLE_GROUP,control_flags),request_id)

def battle_abilities_notice(identity,map_id,request_id,attack_count=0,spell_count=0,abilities=()):
    # Original 52C2F8 reads counters at20/24, count at28, then 16-byte rows.
    # Empty ability rows are explicitly supported by its count<=0 branch.
    rows=tuple(abilities)
    if len(rows)>128 or not 0<=attack_count<=128 or not 0<=spell_count<=128:
        raise ValueError('Bounded battle ability counters required')
    body=bytes(3)+struct.pack('<8I',*identity,map_id,*BATTLE_GROUP,attack_count,spell_count,len(rows))
    for row in rows:
        if len(row)!=4 or any(not isinstance(v,int) or not 0<=v<=0xffffffff for v in row) or row[3]>128:
            raise ValueError('Expected a bounded original 16-byte ability row')
        body+=struct.pack('<4I',*row)
    return message(0xa3,body,request_id)

def validate_initialization_ack(payload,opcode,request_id,identity,map_id,group=BATTLE_GROUP):
    if len(payload)!=32:raise ValueError('Original battle acknowledgement must be 32 bytes')
    flags,actual,size,request=struct.unpack_from('<BHHI',payload)
    if flags!=0 or actual!=opcode or size!=32 or request!=request_id:
        raise ValueError('Battle acknowledgement header does not match its pending notice')
    if struct.unpack_from('<5I',payload,12)!=(*identity,map_id,*group):
        raise ValueError('Battle acknowledgement identity/map/group mismatch')
    return True
