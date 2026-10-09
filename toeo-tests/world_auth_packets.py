"""Recovered 0x18/0x19 world-controller admission stage, not map bootstrap."""
import struct
from account_packets import message


def world_admission_request(network_parameter,ticket,request_id=0xffffffff):
    if not 0<=network_parameter<=0xffff or not 1<=ticket<=0xffff:
        raise ValueError('World admission uses a 16-bit network parameter and nonzero 16-bit ticket')
    return message(0x18,struct.pack('<HH',network_parameter,ticket),request_id)


def world_admission_ack(request_id):
    return message(0x19,b'',request_id)


def parse_world_admission(payload):
    if len(payload)!=13 or struct.unpack_from('<HH',payload,1)!=(0x18,13):
        raise ValueError('Unexpected world admission packet')
    return struct.unpack_from('<HH',payload,9)


def world_account_request(account_id,request_id=0xffffffff):
    if not 1<=account_id<=0xffffffff:raise ValueError('Account ID must be nonzero uint32')
    return message(4,struct.pack('<I',account_id),request_id)


def world_account_ack(request_id):
    # Native 61fdf0 maps 0x11 to zero-payload query correlation.
    return message(0x11,b'',request_id)


def parse_world_account(payload):
    if len(payload)!=13 or struct.unpack_from('<HH',payload,1)!=(4,13):
        raise ValueError('Unexpected world account-control packet')
    account_id=struct.unpack_from('<I',payload,9)[0]
    if not account_id:raise ValueError('Zero account ID')
    return account_id
