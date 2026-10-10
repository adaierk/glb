"""Original AA start and A8 input layouts; command authority remains server-side."""
import struct
from account_packets import message

ATTACK_COMMAND=10004

def battle_start_notice(map_id,group,request_id):
    # Original 52C8AA looks up (map, group) then calls pool 5146A0 once.
    return message(0xaa,bytes(3)+struct.pack('<3I',map_id,*group),request_id)

def parse_attack_request(payload):
    if len(payload)!=56:raise ValueError('Original A8 requires 56 bytes')
    opcode,size,request_id=struct.unpack_from('<HHI',payload,1)
    if payload[0]!=0 or opcode!=0xa8 or size!=len(payload):raise ValueError('Invalid A8 header')
    words=struct.unpack_from('<11I',payload,12)
    return dict(request_id=request_id,map_id=words[0],group=words[1:3],
                identity=words[3:5],command=words[5],target=words[6:8],
                client_tick=words[8],client_date=words[9:11])

def validate_attack_request(request,identity,map_id,group,target):
    if request['identity']!=tuple(identity) or request['map_id']!=map_id or request['group']!=tuple(group):
        raise ValueError('Character, map or active battle group mismatch')
    if target is None or request['target']!=tuple(target) or tuple(target)==tuple(identity):
        raise ValueError('Attack target was not selected in this battle')
    if request['command']!=ATTACK_COMMAND:raise ValueError('Unsupported original battle command')
