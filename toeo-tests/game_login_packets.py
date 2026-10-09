"""Game-specific prelogin 0x33 and response layout recovered from the login UI."""
import struct
import zlib
from account_packets import encode_string, message


def native_crc(data):
    return zlib.crc32(data,0xffffffff)^0xffffffff


def game_login_request(username,password,account_id=0):
    p=bytearray(176)
    p[:9]=message(0x33,bytes(167))[:9]
    struct.pack_into('<HHIII',p,16,176,97,0x10512210,0x1000007e,account_id)
    p[32:102]=encode_string(username)
    p[102:172]=encode_string(password)
    struct.pack_into('<I',p,12,native_crc(p[16:]))
    return bytes(p)


def game_login_reply(username,net_uid=1,account_id=1,request_id=1):
    p=bytearray(97)
    p[:9]=message(0x34,bytes(88),request_id)[:9]
    # Signed result at +0xa: 0 and 1 take the native accepted branch.
    struct.pack_into('<h',p,10,0)
    p[16:86]=encode_string(username)
    struct.pack_into('<II',p,88,net_uid,account_id)
    # Native 530687 copies 0x60 bytes for response opcode 0x34.
    # 52a667's first-channel fallback reads this field as the copy length.
    struct.pack_into('<I',p,12,96)
    return bytes(p)
