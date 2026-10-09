"""Original 4F6CE0 use request and B2 / 526610 vitality record layout."""
import struct
from account_packets import message
from world_map_packets import record


def parse_item_use_request(payload):
    if len(payload)!=76: raise ValueError('Native item-use request must be 76 bytes')
    op,size,request_id=struct.unpack_from('<HHI',payload,1)
    sequence=struct.unpack_from('<I',payload,12)[0]
    map_id,first,second=struct.unpack_from('<III',payload,28)
    item=struct.unpack_from('<IIII',payload,40)
    location,slot,count,target1,target2=struct.unpack_from('<IiIII',payload,56)
    # Native inventory double-click uses count 0; /item uses count 1.
    if op!=0x55 or size!=76 or not request_id or not sequence or location!=2 or slot < -1 or count not in (0,1):
        raise ValueError('Unsupported native item-use header, location or quantity')
    return {'opcode':op,'request_id':request_id,'sequence':sequence,'map_id':map_id,
        'identity':(first,second),'item':item,'location':location,'slot':slot,
        'count':count,'target':(target1,target2)}


def vitals_notice(identity,map_id,vitals):
    tail=bytearray()
    # max HP first: the original current-HP setter clamps to it.
    for kind,key in ((0x6d,'max_hp'),(0x6c,'hp'),(0x70,'tp')):
        r=record(kind,8);struct.pack_into('<I',r,4,vitals[key]);tail.extend(r)
    # Targeted TP record updates both current and maximum values.
    r=record(0x72,20);struct.pack_into('<IIII',r,4,*identity,vitals['tp'],vitals['max_tp']);tail.extend(r)
    tail.extend(bytes(4))
    b=bytearray(message(0xb2,bytes(31+len(tail)),0xffffffff))
    struct.pack_into('<IIIIIII',b,12,len(b),map_id,0,0,*identity,0)
    b[40:]=tail
    return bytes(b)
