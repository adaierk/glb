"""Recovered original inventory and trade packet layouts, with local rules.

Native item templates/icons are unresolved. NAME: is an original item property
handled by 51D930, not an injected display string. Initial money, stack limit,
bag capacity and half-price resale are provisional OFFLINE rules.
"""
import struct
from account_packets import message
from world_map_packets import record

LOCAL_INITIAL_MONEY=5000
LOCAL_STACK_LIMIT=20
LOCAL_BAG_CAPACITY=32
MAX_NATIVE_MONEY=10000000


def inventory_records(snapshot):
    header=record(0x36,16)
    struct.pack_into('<III',header,4,1,0,snapshot['capacity'])
    result=bytearray(header)
    for slot,item in enumerate(snapshot['items']):
        identity=item['identity']
        group=record(0x37,44)
        struct.pack_into('<II',group,4,2,slot)
        struct.pack_into('<IIII',group,0x1c,*identity)
        attributes=record(0x38,84)
        struct.pack_into('<IIII',attributes,4,*identity)
        struct.pack_into('<IIIII',attributes,0x14,item['catalog_index']+1,1,0,0,1)
        struct.pack_into('<hhh',attributes,0x28,item['quantity'],LOCAL_STACK_LIMIT,0)
        struct.pack_into('<IIII',attributes,0x34,0,item['buy_price'],item['sell_price'],0)
        name=('NAME:'+item['name']+';').encode('utf-16le')+b'\0\0'
        properties=record(0x39,(28+len(name)+3)&~3)
        struct.pack_into('<IIII',properties,4,*identity)
        properties[28:28+len(name)]=name
        result.extend(group);result.extend(attributes);result.extend(properties)
        result.extend(record(0x3c,4))
    result.extend(record(0x3d,4))
    return bytes(result)


def inventory_notice(identity,map_id,snapshot):
    money=record(0x6b,8);struct.pack_into('<I',money,4,snapshot['money'])
    tail=bytes(money)+inventory_records(snapshot)+bytes(4)
    b=bytearray(message(0x6b,bytes(23+len(tail)),0xffffffff))
    struct.pack_into('<IIIII',b,12,len(b),map_id,*identity,0)
    b[32:]=tail
    return bytes(b)


def transaction_reply(sequence,money,status=0):
    # 52B86B -> 4FAB30 -> 4F9720 releases the original pending command.
    # Record 50 location 2 updates the checksum-protected player wallet.
    tail=bytearray()
    if status==0:
        wallet=record(0x50,12);struct.pack_into('<II',wallet,4,2,money)
        tail.extend(wallet)
    tail.extend(bytes(4))
    b=bytearray(message(0x67,bytes(27+len(tail)),0xffffffff))
    struct.pack_into('<IIhh',b,12,sequence,len(b),status,0)
    b[36:]=tail
    return bytes(b)


def parse_trade_request(payload):
    if len(payload)<40:raise ValueError('Short trade request')
    op,size,req=struct.unpack_from('<HHI',payload,1)
    if op not in (0xde,0xdf) or size!=len(payload) or req!=0xffffffff:
        raise ValueError('Unsupported trade header')
    seq,first,second,map_id,npc1,npc2,count=struct.unpack_from('<IIIIIII',payload,12)
    stride=8 if op==0xde else 24
    if seq==0 or not 1<=count<=4 or size!=40+count*stride:
        raise ValueError('Invalid native sequence, batch size or line length')
    lines=[]
    for offset in range(40,size,stride):
        values=struct.unpack_from('<'+'I'*(stride//4),payload,offset)
        if op==0xde:
            index,quantity=values
            lines.append({'catalog_index':index,'quantity':quantity})
        else:
            *identity,location,quantity=values
            if location!=2:raise ValueError('Unsupported inventory location')
            lines.append({'identity':tuple(identity),'quantity':quantity})
        if not 1<=quantity<=LOCAL_STACK_LIMIT:raise ValueError('Local quantity limit')
    return {'opcode':op,'sequence':seq,'identity':(first,second),'map_id':map_id,
            'merchant':(npc1,npc2),'lines':lines}
