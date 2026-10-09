"""TOEO network-user bootstrap frames, derived from the original PC binary.

This is a transport/session initialization candidate, not account authorization.
"""
import socket
import struct

MAGIC = bytes.fromhex('12345678')


def envelope(opcode, payload, sequence=0xffff):
    length = 20 + len(payload) + 4
    header = bytearray(20)
    header[:4] = MAGIC
    struct.pack_into('<HHHH', header, 4, length, opcode, length - 4, sequence)
    return bytes(header) + payload + MAGIC


def user_record(member_id=1, net_uid=1, sys_type=2, encoding=0):
    if sys_type not in (1, 2):
        raise ValueError('Original handler accepts only system types 1 and 2')
    if encoding not in (0, 2, 3):
        raise ValueError('Original allocator accepts modes 0, 2 and 3')
    # t_NNetDataAddOne: two IDs, optional data pointer/lengths, mode/type/flags.
    return struct.pack('<IIIHHBBBB', member_id, net_uid, 0, 0, 0,
                       encoding, sys_type, 0, 0)


def bootstrap402(records=None, my_member_id=1, port=11100):
    if records is None:
        records = [user_record(member_id=my_member_id)]
    if any(len(r) != 20 for r in records):
        raise ValueError('Each network-user record is exactly 20 bytes')
    # Original 0x60B4F0 locates record i at packet+0x28+i*0x14.
    # 0x6128D3 compares its first ID with packet+0x24 to identify ourselves.
    prefix = struct.pack('<II', len(records), 0)
    prefix += socket.inet_aton('127.0.0.1') + struct.pack('!H', port)
    prefix += struct.pack('<HI', 0, my_member_id)
    return envelope(0x402, prefix + b''.join(records))


def add_user401(member_id=2, net_uid=2):
    return envelope(0x401, user_record(member_id, net_uid))
