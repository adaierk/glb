"""Measured native endpoint control packets; server values are local assignments."""
import struct
from account_packets import message

def parse_endpoint_request(payload):
    if len(payload)!=17 or struct.unpack_from('<HH',payload,1)!=(0x0d,17):
        raise ValueError('Unexpected endpoint request')
    return payload[9:15],struct.unpack_from('<H',payload,15)[0]

def endpoint_reply(endpoint,tcp_port,network_parameter,uid,version,nonce,ip,request_id):
    if len(endpoint)!=6 or not 1<=tcp_port<=65535 or not 1<=uid<=0xffffffff:
        raise ValueError('Invalid native endpoint descriptor')
    return message(0x0f,struct.pack('<B6sBHHIIII',1,endpoint,0,tcp_port,network_parameter,
                                  uid,version,nonce,ip),request_id)

def parse_endpoint_attachment(payload):
    if len(payload)!=20 or struct.unpack_from('<HH',payload,1)!=(0x10,20):
        raise ValueError('Unexpected endpoint attachment')
    return struct.unpack_from('<BHII',payload,9)
