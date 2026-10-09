"""Recovered creation 37/38 and deletion 39/3a packets."""
import hashlib
import struct
from account_packets import message


def wide_checksum(raw):
    if len(raw)%2:raise ValueError('Odd UTF-16 data')
    acc=0xffff
    for i,(word,) in enumerate(struct.iter_unpack('<H',raw)):
        acc^=((word+i)*0x8320)&0xffffffff
    return (~acc)&0xffff


def encode_name(name):
    raw=name.encode('utf-16le')
    if not raw or len(raw)>62 or '\0' in name:
        raise ValueError('Original character names require 1..31 UTF-16 code units')
    name.encode('cp932')  # native selector also requires a representable CP932 name
    key=wide_checksum(raw);mask=((~(key>>8))^key)&255
    encoded=bytes((((b+i-0x20)&255)^mask) for i,b in enumerate(raw))
    return struct.pack('<HH',key,len(raw)//2)+encoded+bytes(64-len(raw))


def decode_name(field):
    if len(field)!=68:raise ValueError('Native character name field must occupy 68 bytes')
    key,n=struct.unpack_from('<HH',field)
    if not 1<=n<=31:raise ValueError('Invalid character name size')
    mask=((~(key>>8))^key)&255
    raw=bytes((((b^mask)-i+0x20)&255) for i,b in enumerate(field[4:4+n*2]))
    if wide_checksum(raw)!=key:raise ValueError('Character name checksum mismatch')
    name=raw.decode('utf-16le')
    if '\0' in name:raise ValueError('Embedded NUL in character name')
    name.encode('cp932')
    return name


def create_character_request(name,parameters=(1,1,0,0,0,0,0,0,0,1),identity=(0,0),request_id=0xffffffff):
    if len(parameters)!=10 or len(identity)!=2:raise ValueError('Unexpected creation parameter count')
    p=bytearray(156);p[:9]=message(0x37,bytes(147),request_id)[:9]
    struct.pack_into('<II',p,32,*identity)
    p[40:108]=encode_name(name)
    # Client copies profile+54, inserts level 1, then profile+50 and appearance/other parameters.
    struct.pack_into('<10I',p,108,parameters[0],1,*parameters[1:9])
    struct.pack_into('<II',p,148,0xffffffff,parameters[9])
    p[12:32]=hashlib.sha1(p[32:]).digest()
    return bytes(p)


def parse_create_request(p):
    if len(p)!=156 or struct.unpack_from('<HH',p,1)!=(0x37,156):
        raise ValueError('Unexpected creation packet header')
    if p[12:32]!=hashlib.sha1(p[32:]).digest():raise ValueError('Creation SHA-1 mismatch')
    if struct.unpack_from('<I',p,112)[0]!=1 or struct.unpack_from('<I',p,148)[0]!=0xffffffff:
        raise ValueError('Unexpected native creation constants')
    return {'name':decode_name(p[40:108]),'identity':struct.unpack_from('<II',p,32),
            'parameters':(struct.unpack_from('<I',p,108)[0],)+struct.unpack_from('<8I',p,116)+
                         (struct.unpack_from('<I',p,152)[0],)}


def mutation_reply(opcode,request_id=1,status=0):
    if opcode not in (0x38,0x3a):raise ValueError('Unexpected mutation answer')
    return message(opcode,b'\0'+struct.pack('<h',status),request_id)


def delete_character_request(character_id,request_id=0xffffffff):
    return message(0x39,bytes(3)+struct.pack('<II',*character_id),request_id)
