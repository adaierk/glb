"""Original compressed ED item-source request and EE / 4D7DB0 reply."""
import struct
from account_packets import message
from world_map_packets import record
from world_item_definitions import icon_selector,RECOVERY
from world_inventory_packets import LOCAL_STACK_LIMIT


def parse_item_source_request(payload):
    if len(payload)<36:raise ValueError('Short item-source request')
    op,size,request_id=struct.unpack_from('<HHI',payload,1)
    fixed,map_id,first,second,count=struct.unpack_from('<IIIII',payload,12)
    if op!=0xed or size!=len(payload) or fixed!=len(payload) or not request_id or not 1<=count<=32 or size!=32+4*count:
        raise ValueError('Invalid item-source request bounds')
    return {'request_id':request_id,'map_id':map_id,'identity':(first,second),
        'catalog_ids':struct.unpack_from('<'+'I'*count,payload,32)}


def item_source_reply(request,stock):
    tail=bytearray()
    for catalog_id in request['catalog_ids']:
        if not 1<=catalog_id<=len(stock):raise ValueError('Unknown local item-source ID')
        item=stock[catalog_id-1];kind,offset=icon_selector(item['name'])
        create=record(0x3e,36);struct.pack_into('<I',create,4,catalog_id);tail.extend(create)
        attributes=record(0x38,84)
        struct.pack_into('<IIIII',attributes,0x14,catalog_id,1,0,0,1)
        struct.pack_into('<hhh',attributes,0x28,1,LOCAL_STACK_LIMIT,offset)
        struct.pack_into('<IIII',attributes,0x34,kind,item['price_gald'],item['price_gald']//2,0)
        tail.extend(attributes)
        hp,tp=RECOVERY.get(item['name'],(0,0))
        description=(f'HP {hp} / TP {tp}' if (hp or tp) else 'Local effect not restored')
        for rec,text in ((0x39,'NAME:'+item['name']+';'),(0x3f,description)):
            raw=text.encode('utf-16le')+b'\0\0';r=record(rec,(28+len(raw)+3)&~3)
            struct.pack_into('<I',r,0x14,catalog_id);r[28:28+len(raw)]=raw;tail.extend(r)
        tail.extend(record(0x3c,4))
    tail.extend(bytes(4))
    b=bytearray(message(0xee,bytes(19+len(tail)),request['request_id']))
    struct.pack_into('<IIII',b,12,len(b),request['map_id'],*request['identity'])
    b[28:]=tail
    return bytes(b)
