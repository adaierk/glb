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
SHOP_GRID=(10,12)
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
