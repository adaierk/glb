"""Recovered NetFrmCL1 account payloads. Transport wrapping is separate."""
import struct


def checksum(raw):
    acc = 0xffff
    for i, byte in enumerate(raw[:64]):
        signed = byte if byte < 128 else byte - 256
        acc ^= ((signed + i) * 0x8320) & 0xffffffff
    return (~acc) & 0xffff


def encode_string(text):
    raw = text.encode('cp932')
    if not raw or len(raw) > 64 or b'\x00' in raw:
        raise ValueError('Native account strings require 1..64 non-NUL CP932 bytes')
    key = checksum(raw)
    mask = ((~(key >> 8)) ^ key) & 0xff
    encrypted = bytes((((b + i - 0x20) & 0xff) ^ mask) for i,b in enumerate(raw))
    return struct.pack('<HH', key, len(raw)) + encrypted + bytes(66-len(raw))


def decode_string(field):
    if len(field) != 70:
        raise ValueError('String field must be 70 bytes')
    key, count = struct.unpack_from('<HH', field)
    if count > 64:
        raise ValueError('Invalid account string length')
    mask = ((~(key >> 8)) ^ key) & 0xff
    raw = bytes((((b ^ mask) - i + 0x20) & 0xff) for i,b in enumerate(field[4:4+count]))
    if checksum(raw) != key:
        raise ValueError('Account string checksum mismatch')
    return raw.decode('cp932')


def message(opcode, body, request_id=0xffffffff):
    return struct.pack('<BHHI', 0, opcode, 9+len(body), request_id) + body


def login_request(username, password):
    return message(0x20, encode_string(username) + encode_string(password))


def login_ok_body(net_uid=1, account_id=1, login_sid=1, username='archive001'):
    """105-byte success reply: native 61af20 selects size 0x69 for notice type 1."""
    if not login_sid:
        raise ValueError('Native login requires a nonzero session ID')
    return struct.pack('<IIIII', 1, 1, net_uid, account_id, login_sid) + encode_string(username) + bytes(6)
