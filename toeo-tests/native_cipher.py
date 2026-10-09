"""622930/622900 transport cipher, measured against the original executable."""
import struct
import time
import zlib

KEY = 0x8823729c
PERM = bytes.fromhex('ac2f75c043fbc36709d315f2245746d8588c3ac1e627ae51a5194d489473d0f3c5fe4faf5263b11d938ea720b97f1fcaf497a3cb72b71c2280a4358526e81184692aba780141e7a9392366770b5b79aa544406c483cc64b44e8fe317cf8d553031455f5e0071b2a25d62cd7095c98a2bbb823ede7bd1329b0e290a5668023350b613b8bc1e187d03e26b0d289ac2f8ec3d6004ed8bfc6d4b10989d6e76bd53a1a0e4d54712a66ff981df2cd2efead6d7d4eb9c1bd9b589492eda6cadc76121ff7ebe88a874b0f192ddfd6542969e91c65c59e0db3f6abfee40dc14167a87c8051a4a34ab373b7c083c90383699b3f607f09f4ce186e5cee95afaf50f0c2d25f7')
assert len(PERM) == len(set(PERM)) == 256
INV = bytes(PERM.index(i) for i in range(256))

def _offset(key, tick):
    return ((key >> 17) + (tick >> 16) + ((key & 255) << 7) + (tick & 255)) & 255

def encode(payload, tick=None, padding=0, key=KEY):
    if not 0 < len(payload) <= 60000 or not 0 <= padding < 12:
        raise ValueError('Invalid cipher input size or padding')
    tick = int(time.monotonic()*1000) & 0xffffffff if tick is None else tick
    padded = (len(payload)+padding+3) & ~3
    plain = payload + bytes(PERM[i & 255] for i in range(len(payload), padded)) + struct.pack('<I',len(payload))
    plain += struct.pack('<I',zlib.crc32(plain))
    offset = _offset(key,tick)
    wire = bytes(PERM[(v+offset)&255] for v in plain) + struct.pack('<I',tick)
    return bytes(v ^ (key >> (8*(i&3)) & 255) for i,v in enumerate(wire))

def decode(wire, key=KEY):
    if len(wire)<16 or len(wire)%4 or len(wire)>60024:
        raise ValueError('Invalid cipher frame size')
    plain = bytes(v ^ (key >> (8*(i&3)) & 255) for i,v in enumerate(wire))
    tick, = struct.unpack_from('<I',plain,len(plain)-4)
    offset = _offset(key,tick)
    plain = bytes((INV[v]-offset)&255 for v in plain[:-4])
    size,crc = struct.unpack_from('<II',plain,len(plain)-8)
    if crc != zlib.crc32(plain[:-4]):
        raise ValueError('Cipher CRC mismatch')
    if not 0<size<=len(plain)-8 or len(plain)-8-size>14:
        raise ValueError('Invalid cipher payload length')
    return plain[:size]
