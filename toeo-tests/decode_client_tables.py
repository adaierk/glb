"""Read preserved TOEO IDTB/NNTB/SMS2 assets without changing original files.

The original x86 routines use Blowfish ECB with little-endian DWORD blocks.
This analysis helper uses libcrypto; it is not a game/server dependency.
"""
import argparse
import ctypes
import ctypes.util
import hashlib
import json
import struct
from pathlib import Path


def decrypt_blocks(data, key):
    if len(data) % 8:
        raise ValueError('Blowfish input must contain complete 8-byte blocks')
    crypto = ctypes.CDLL(ctypes.util.find_library('crypto'))
    crypto.BF_set_key.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    crypto.BF_ecb_encrypt.argtypes = [ctypes.c_void_p] * 3 + [ctypes.c_int]
    state = ctypes.create_string_buffer(4168)
    crypto.BF_set_key(state, len(key), key)
    output = bytearray()
    for pos in range(0, len(data), 8):
        block = data[pos:pos+8]
        source = block[:4][::-1] + block[4:][::-1]
        target = ctypes.create_string_buffer(8)
        crypto.BF_ecb_encrypt(source, target, state, 0)
        output.extend(target.raw[:4][::-1] + target.raw[4:][::-1])
    return bytes(output)


def decode_table(path):
    data = Path(path).read_bytes()
    magic = data[:4]
    meta = {'file': Path(path).name, 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
            'format': magic.decode('ascii'), 'original_unchanged': True}
    if magic == b'SMS2':
        count = struct.unpack_from('<I', data, 8)[0]
        if 12 + count * 16 > len(data):
            raise ValueError('SMS2 index exceeds file')
        rows = []
        for index in range(count):
            ident, offset, size, characters = struct.unpack_from('<IIII', data, 12 + index * 16)
            if offset < 12 + count * 16 or offset + size > len(data) or characters * 2 > size:
                raise ValueError('Invalid SMS2 string bounds')
            text = decrypt_blocks(data[offset:offset+size], data[:12])
            rows.append({'id': ident, 'text': text[:characters*2].decode('utf-16le')})
        meta.update(count=count, scope='Client UI messages; not official NPC spawn or item template database')
        return meta, rows
    if magic not in (b'IDTB', b'NNTB'):
        raise ValueError('Unsupported preserved table')
    hash_pos, length_pos, hash_start, key = ((0x30, 0x44, 0x48, b'idtable text')
        if magic == b'IDTB' else (0x18, 0x2c, 0x30, b'nntable text'))
    hashed_length = struct.unpack_from('<I', data, length_pos)[0]
    if hash_start + hashed_length > len(data) or hashlib.sha1(data[hash_start:hash_start+hashed_length]).digest() != data[hash_pos:hash_pos+20]:
        raise ValueError('Original table SHA1 does not match its header')
    count, offset, row_count, row_offset = struct.unpack_from('<IIII', data, 8)
    plain = bytearray(data)
    for index in range(count):
        if offset + 4 > len(data):
            raise ValueError('Missing encrypted block length')
        size = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        if offset + size > len(data):
            raise ValueError('Encrypted string exceeds file')
        plain[offset:offset+size] = decrypt_blocks(data[offset:offset+size], key)
        offset += size
    if offset != len(data) or row_offset + row_count * 8 > len(data):
        raise ValueError('Original table structure is inconsistent')
    def string_at(pos):
        if not hash_start <= pos < len(plain):
            raise ValueError('Invalid table string offset')
        return bytes(plain[pos:]).split(b'\0', 1)[0].decode('cp932')
    rows = []
    for index in range(row_count):
        left, right = struct.unpack_from('<II', plain, row_offset + index * 8)
        rows.append({'id': left, 'name': string_at(right)} if magic == b'IDTB'
                    else {'name': string_at(left), 'resource_name': string_at(right)})
    meta.update(count=row_count, encrypted_strings=count, original_sha1_verified=True,
                scope='Model/resource symbolic names; not verified NPC spawn or item template data')
    return meta, rows


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('resource_directory'); p.add_argument('--out', required=True)
    args = p.parse_args(); output = Path(args.out); output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name in ('cid0.idt', 'cid1.idt', 'cty2rs.nnt', 'toeomsg_jp.sms', 'toeomsg2_jp.sms', 'toeomsg3_jp.sms'):
        meta, rows = decode_table(Path(args.resource_directory) / name)
        (output / (name + '.json')).write_text(json.dumps({'metadata': meta, 'rows': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
        manifest.append(meta)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))
