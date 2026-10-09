"""Character-list layout recovered from 438360, 5306c5 and 438690.

Populated records use recovered core/model-loader fields; rendering and world
fields still require validation against original resources.
"""
import struct
from account_packets import message


def character_list_request():
    return message(0x35,b'')


def character_record(native_fields,name):
    if len(native_fields)!=0xf8:
        raise ValueError('Native character fields must occupy 248 bytes')
    # 4387DC assigns this tail to std::basic_string<unsigned short>, confirmed
    # by the MSVCP71 import at 6E2348 and actual Windows selector rendering.
    raw=name.encode('utf-16le')
    if not raw or '\0' in name or len(raw)>62:
        raise ValueError('Character name must occupy 1..31 UTF-16 code units')
    size=(4+len(native_fields)+len(raw)+2+3)&~3
    return struct.pack('<HH',0x20,size//4)+native_fields+raw+bytes(size-252-len(raw))


def character_list_reply(records=(),available_slots=3,selected_id=(0,0),request_id=1,status=0):
    if len(records)>3 or not 0<=available_slots<=3-len(records):
        raise ValueError('Original character selector has three slots')
    answer=bytearray(36)
    answer[:9]=message(0x36,bytes(27),request_id)[:9]
    struct.pack_into('<h',answer,16,status)
    struct.pack_into('<IIII',answer,20,len(records),available_slots,*selected_id)
    answer.extend(b''.join(records))
    answer.extend(bytes(4))  # zero-type record terminates the native record chain
    struct.pack_into('<H',answer,3,len(answer))
    struct.pack_into('<I',answer,12,len(answer))  # native response correlator copy size
    return bytes(answer)


def select_character_request(character_id=(123,456),options=0):
    return message(0x3b,bytes(3)+struct.pack('<III',*character_id,options))


def select_character_reply(route_fields,link_records,request_id=1,status=0):
    """112-byte selection answer; nine route DWORDs remain partly unconfirmed.

    This encoder is a research fixture, not a live map endpoint implementation.
    Original 437da0 copies nine DWORDs and a vector of up to five DWORD triplets.
    World conversion recovers triplets as IPv4/UDP port/TCP port; no live world
    authentication or map endpoint is implemented by this encoder.
    """
    if len(route_fields)!=9 or not 0<=len(link_records)<=5 or any(len(r)!=3 for r in link_records):
        raise ValueError('Selection result requires 9 route DWORDs and at most 5 link triplets')
    answer=bytearray(112)
    answer[:9]=message(0x3c,bytes(103),request_id)[:9]
    struct.pack_into('<h',answer,10,status)
    struct.pack_into('<9I',answer,12,*route_fields)
    struct.pack_into('<I',answer,48,len(link_records))
    for i,record in enumerate(link_records):struct.pack_into('<III',answer,52+12*i,*record)
    return bytes(answer)
