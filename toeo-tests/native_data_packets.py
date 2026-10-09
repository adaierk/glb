"""Plain NNet 0x0405 data frames, checked against original x86 code."""
import struct
from native_handshake_packets import MAGIC


def data405(payload, sender_index, sender_uid, target_index=1, target_uid=1, route=0xffff, flags=4):
    if len(payload) > 60000:
        raise ValueError('Payload too long')
    frame = bytearray(40+len(payload))
    frame[:4] = MAGIC
    struct.pack_into('<HHH',frame,4,len(frame),0x405,len(frame)-4)
    struct.pack_into('<H',frame,10,sender_index)
    struct.pack_into('<I',frame,14,sender_uid)
    frame[18]=flags
    frame[19]=1 if route==0xffff else 0
    struct.pack_into('<HHI',frame,20,route,target_index,target_uid)
    struct.pack_into('<HHI',frame,28,sender_index,len(payload),sender_uid)
    frame[36:36+len(payload)]=payload
    frame[-4:]=MAGIC
    return bytes(frame)


def parse405(frame):
    if len(frame)<40 or frame[:4]!=MAGIC or frame[-4:]!=MAGIC:
        raise ValueError('Malformed data frame')
    length,op,tail=struct.unpack_from('<HHH',frame,4)
    if length!=len(frame) or op!=0x405 or tail!=length-4:
        raise ValueError('Malformed data header')
    index,n,uid=struct.unpack_from('<HHI',frame,28)
    if n!=length-40:
        raise ValueError('Payload length mismatch')
    payload=frame[36:-4]
    if len(payload)<9 or struct.unpack_from('<H',payload,3)[0]!=len(payload):
        raise ValueError('Not a plain application message (compression/encryption unsupported)')
    if payload[0]&0x80:
        raise ValueError('Encrypted application message requires runtime evidence')
    return {'sender_index':index,'sender_uid':uid,'flags':frame[18],
            'route':struct.unpack_from('<H',frame,20)[0],
            'opcode':struct.unpack_from('<H',payload,1)[0],
            'request_id':struct.unpack_from('<I',payload,5)[0],'payload':payload}


class FrameStream:
    """Bounded TCP decoder; incomplete input is retained, malformed input rejected."""
    def __init__(self):
        self.pending=bytearray()

    def feed(self,data):
        self.pending.extend(data)
        result=[]
        while len(self.pending)>=6:
            if self.pending[:4]!=MAGIC:
                raise ValueError('Missing NNet magic; inspect transport mode')
            n=struct.unpack_from('<H',self.pending,4)[0]
            if n<24 or n>65535:
                raise ValueError('Invalid NNet length')
            if len(self.pending)<n:break
            frame=bytes(self.pending[:n]);del self.pending[:n]
            if frame[-4:]!=MAGIC or struct.unpack_from('<H',frame,8)[0]!=n-4:
                raise ValueError('Invalid NNet tail')
            result.append(frame)
        return result
