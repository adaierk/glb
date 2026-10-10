"""Original AA start and A8 input layouts; command authority remains server-side."""
import math,struct
from world_map_packets import record
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

def action_record(identity,position,direction,command,target=(0,0)):
    if direction not in (2,6):raise ValueError('Original horizontal battle direction required')
    b=record(0x5a,52)
    struct.pack_into('<IIff8I',b,4,*identity,*position,direction,command,0,0,*target,2,0)
    return bytes(b)

def actor_action_notice(map_id,group,identity,action,request_id=0xffffffff):
    if len(action)!=52 or struct.unpack_from('<HH',action)!=(0x5a,13) or struct.unpack_from('<II',action,4)!=tuple(identity):
        raise ValueError('Original actor action record mismatch')
    b=bytearray(message(0xb2,bytes(31)+action+bytes(4),request_id))
    struct.pack_into('<6I',b,12,len(b),map_id,*group,*identity)
    return bytes(b)

def parse_battle_move_request(payload,identity,map_id,group):
    if len(payload)!=92 or payload[0]!=0 or struct.unpack_from('<HH',payload,1)!=(0xa7,92) or struct.unpack_from('<I',payload,12)[0]!=92:
        raise ValueError('Invalid original A7 packet')
    if struct.unpack_from('<3I',payload,16)!=(map_id,*group):
        raise ValueError('Movement map or active battle mismatch')
    action=payload[40:]
    if struct.unpack_from('<HH',action)!=(0x5a,13) or struct.unpack_from('<II',action,4)!=tuple(identity):
        raise ValueError('Movement character mismatch')
    x,y=struct.unpack_from('<ff',action,12);direction,command,*extra=struct.unpack_from('<8I',action,20)
    if not all(math.isfinite(v) for v in (x,y)) or not 0<=x<=1600 or y!=0:
        raise ValueError('Movement outside original local battle arena')
    if direction not in (2,6) or command!=1 or extra!=[0,0,0,0,2,0]:
        raise ValueError('Unsupported original movement state')
    return dict(request_id=struct.unpack_from('<I',payload,5)[0],identity=tuple(identity),map_id=map_id,group=tuple(group),position=(x,y),direction=direction,action=action)

def attack_action_notice(attack,position):
    direction=2 if position[0]<580 else 6
    action=action_record(attack['identity'],position,direction,attack['command'],attack['target'])
    return actor_action_notice(attack['map_id'],attack['group'],attack['identity'],action)
