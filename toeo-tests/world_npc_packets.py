"""A local merchant projected into original CreateActorCl (51C1E0).

Placement and identity are local recovery content, not recovered official data.
The appearance uses the same original humanoid resource path as player models.
"""
import struct
from account_packets import message
from character_store import native_character_fields
from character_mutation_packets import encode_name
from world_map_packets import record,LOCAL_MAP_ID

SHOP_IDENTITY=(0x70000001,1)
SHOP_GRID=(12,8)
SHOP_NAME='Archive Shop'

def shop_actor_records():
    b=record(0x22,0xd0)
    # 51C31F: actor category. 51C2F3: two-DWORD entity identity.
    struct.pack_into('<I',b,4,2)
    struct.pack_into('<II',b,12,*SHOP_IDENTITY)
    struct.pack_into('<hh',b,0x18,*SHOP_GRID)
    b[0x23]=0xff # original signed direction -1 (automatic)
    b[0x24:0x28]=bytes((1,0,0,1))
    b[0x30:0x74]=encode_name(SHOP_NAME)
    fields=native_character_fields(SHOP_IDENTITY,SHOP_NAME,(1,1,0,0,0,0,0,0,0,0))
    b[0x74:0x8c]=fields[0x30:0x48]
    struct.pack_into('<IIII',b,0x8c,100,100,30,30)
    # 51CB14 creates CActorExtParamCl_Shop; this chunk has no extra fields.
    return bytes(b)+bytes(record(0x2f,4))+bytes(4)

def shop_actor_notice():
    tail=shop_actor_records()
    b=bytearray(message(0x3b,bytes(23+len(tail)),0xffff)[:32])
    struct.pack_into('<I',b,12,32+len(tail))
    struct.pack_into('<III',b,20,*SHOP_IDENTITY,LOCAL_MAP_ID)
    return bytes(b)+tail

def parse_npc_request(payload):
    """Read original C6/C8 fields, with no synthetic UI command state."""
    if len(payload)<9:raise ValueError('Short NPC request')
    op,size,req=struct.unpack_from('<HHI',payload,1)
    if size!=len(payload):raise ValueError('NPC request size mismatch')
    if op==0xc6 and size==48:
        return dict(opcode=op,request_id=req,identity=struct.unpack_from('<II',payload,12),
                    map_id=struct.unpack_from('<I',payload,20)[0],
                    target=struct.unpack_from('<II',payload,24),
                    grid=struct.unpack_from('<ii',payload,32),
                    extra=struct.unpack_from('<I',payload,40)[0],flags=tuple(payload[44:46]))
    if op==0xc8 and size==44:
        return dict(opcode=op,request_id=req,action=struct.unpack_from('<I',payload,36)[0],
                    identity=struct.unpack_from('<II',payload,16),
                    map_id=struct.unpack_from('<I',payload,24)[0],
                    target=struct.unpack_from('<II',payload,28),
                    extra=struct.unpack_from('<I',payload,12)[0],option=struct.unpack_from('<I',payload,40)[0])
    raise ValueError('Unsupported NPC request')

def npc_selection_reply(request):
    # Original 52CC40: type 4 opens native NPC actions, exact mask 2
    # selects native action 20002 and constructs C8 action 2 itself.
    b=bytearray(message(0xc7,bytes(51),request['request_id']))
    struct.pack_into('<I',b,12,4)
    struct.pack_into('<IIIIIii',b,16,*request['identity'],LOCAL_MAP_ID,*SHOP_IDENTITY,*SHOP_GRID)
    struct.pack_into('<II',b,48,2,0)
    return bytes(b)

def npc_action_reply(request):
    # C9 fixed header, 52CDE7: result 0, original action 2 stops selection.
    b=bytearray(message(0xc9,bytes(39),request['request_id']))
    struct.pack_into('<Ii',b,12,0,0)
    struct.pack_into('<IIIIII',b,20,*request['identity'],LOCAL_MAP_ID,*SHOP_IDENTITY,request['action'])
    return bytes(b)

def shop_open_notice(identity,request_id):
    """Original D6 shop header and empty chunk terminator; no invented goods."""
    b=bytearray(message(0xd6,bytes(43),request_id))
    struct.pack_into('<IIIII',b,12,*identity,LOCAL_MAP_ID,*SHOP_IDENTITY)
    struct.pack_into('<II',b,36,0,0)
    b[44:48]=record(0x9a,4) # required start-group chunk before the terminator
    return bytes(b)
