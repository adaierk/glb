"""Cross-check original pixels and map parser; Windows evidence is separate."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP, UC_X86_REG_EIP
from emulate_session_bootstrap import NativeFixture
from emulate_map_initialization import MapFixture
from decode_original_graphics import lz2_decode
from character_store import native_character_fields
from native_map_geometry import grid_to_point
from world_map_packets import world_initialization_reply
from world_profiles import RASHUAN


def run(binary, minimap):
    data = Path(minimap).read_bytes()
    offset = struct.unpack_from('<I', data, 16)[0]
    width, height, depth, fmt, size, compression, reserved = struct.unpack_from('<HHIIIII', data, offset)
    source = data[offset+24:offset+24+size]
    pixels = lz2_decode(source, width*height*2)
    f = NativeFixture(binary)
    src, dst, length, sp = 0x1050000, 0x1060000, 0x1040000, 0x20ff000
    f.uc.mem_write(src, source)
    f.uc.mem_write(sp, struct.pack('<7I', f.stop, dst, len(pixels), length, src, len(source), 0))
    f.uc.reg_write(UC_X86_REG_ESP, sp)
    f.uc.emu_start(0x5f9880, f.stop, count=6000000)
    assert f.uc.reg_read(UC_X86_REG_EIP) == f.stop
    assert f.uc.reg_read(UC_X86_REG_EAX) & 255 == 1
    assert f.read32(length) == len(pixels)
    assert bytes(f.uc.mem_read(dst, len(pixels))) == pixels
    assert not f.assertions
    m = MapFixture(binary); packet = 0x109a000
    fields = native_character_fields((1, 1), 'Archive', (1, 1, 0, 0, 0, 0, 0, 0, 0, 0))
    reply = world_initialization_reply((1, 1), 'Archive', fields, 1, map_id=RASHUAN.map_id,
        position=grid_to_point(RASHUAN.spawn_grid), label=RASHUAN.label)
    m.uc.mem_write(packet, reply); m.invoke(0x43f090, (packet, packet+40), this=m.ui)
    assert m.read32(m.data+0x14) == RASHUAN.map_id
    assert [m.read32(m.data+0xe0+0x230), m.read32(m.data+0xe0+0x234)] == list(RASHUAN.spawn_grid)
    assert list(m.strings.values())[:3] == ['map/1120108.mpd', 'map/1120108.mpi', 'map/1120108.bnd']
    assert not m.assertions
    return {'passed': True, 'native_minimap_decode': True, 'pixel_sha256': hashlib.sha256(pixels).hexdigest(),
            'minimap_sha256': hashlib.sha256(data).hexdigest(), 'dimensions': [width, height],
            'native_map_record_parse': True, 'map_id': RASHUAN.map_id, 'spawn_grid': list(RASHUAN.spawn_grid),
            'limitations': ['Map parser fixture substitutes constructors/strings/OS/UI/send boundaries',
                           'Visual Wiki map matching is an inference; official server placement unavailable',
                           'These bounded checks do not demonstrate Windows GUI or shop interaction']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('binary'); p.add_argument('minimap'); p.add_argument('--out', required=True)
    a = p.parse_args(); result = run(a.binary, a.minimap)
    Path(a.out).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('ORIGINAL_RASHUAN_PIXELS_AND_MAP_RECORD_PASS')
