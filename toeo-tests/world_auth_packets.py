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


def world_account_ack(request_id,*,broadcast=True):
    # The original primary world wrapper (vtable 7085e4) uses 61fc50,
    # whose 04 account query is correlated by 05. The account wrapper
    # (708614 / 61fdf0) correlates its control queries with 11.
    return message(5 if broadcast else 0x11,b'',request_id)


def parse_world_account(payload):
    if len(payload)!=13 or struct.unpack_from('<HH',payload,1)!=(4,13):
        raise ValueError('Unexpected world account-control packet')
    account_id=struct.unpack_from('<I',payload,9)[0]
    if not account_id:raise ValueError('Zero account ID')
    return account_id
