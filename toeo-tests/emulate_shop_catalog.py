"""Execute original D6 parsing/item construction/name+price assignment.

External C++ strings, resource lookup, UI/transport and collection boundaries
are declared fixture substitutions. Windows GUI verification is separate.
"""
import argparse
import json
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP
from emulate_npc_interaction import InteractionFixture
from world_npc_packets import shop_open_notice
from world_shop_catalog import PREVIEW_SOURCE_KEY, historical_stock


class CatalogFixture(InteractionFixture):
    def __init__(self, binary):
        self.string_ops = {}; self.item_strings = {}; self.items = []
        super().__init__(binary)
        imports = {0x6e2350: 'construct', 0x6e22a0: 'clear',
                   0x6e2348: 'assign', 0x6e23c0: 'append_object'}
        for index, (iat, operation) in enumerate(imports.items()):
            address = 0x10dc000 + index * 16
            self.write32(iat, address); self.string_ops[address] = operation

    def on_code(self, uc, va, size, context):
        sp = uc.reg_read(UC_X86_REG_ESP); obj = uc.reg_read(UC_X86_REG_ECX)
        if va in self.string_ops:
            operation = self.string_ops[va]
            if operation in ('construct', 'clear'):
                self.item_strings[obj] = ''; self.ret(obj)
            elif operation == 'assign':
                p = self.read32(sp+4); value = bytearray()
                while True:
                    word = bytes(uc.mem_read(p, 2)); p += 2
                    if word == b'\0\0': break
                    value.extend(word)
                    if len(value) > 2048: raise ValueError('Fixture string too long')
                self.item_strings[obj] = value.decode('utf-16le'); self.ret(obj, 4)
            else:
                self.item_strings[obj] += self.item_strings[self.read32(sp+4)]
                self.ret(obj, 4)
        elif va == 0x46eaf0:
            # No original item templates have been recovered. Original Windows
            # lookup returns NULL for resource ID zero, independently observed.
            self.ret(0)
        elif va == 0x51ea20:
            item = self.read32(sp+8)
            self.items.append({'name': self.item_strings[item+0x34],
                'price_gald': self.read32(item+0x11c),
                'template_pointer': self.read32(item+0x30),
                'icon_id': self.read32(item+0xa4)})
            self.write32(self.shop+0x11c, len(self.items)); self.ret(len(self.items)-1, 8)
        else:
            super().on_code(uc, va, size, context)


def run(binary):
    source = historical_stock(PREVIEW_SOURCE_KEY)
    fixture = CatalogFixture(binary)
    packet = shop_open_notice((1, 1), 0x70000001, stock=source['stock'])
    fixture.receive(0x52d561, packet)
    expected = [{'name': x['name'], 'price_gald': x['price_gald'],
                 'template_pointer': 0, 'icon_id': 0} for x in source['stock']]
    assert fixture.shop_parse_result == 1 and fixture.items == expected
    assert not fixture.assertions
    return {'passed': True, 'packet_bytes': len(packet), 'native_parse_result': fixture.shop_parse_result,
            'items': fixture.items, 'source_url': source['source_url'],
            'substitutions': ['External C++ string operations', 'Resource lookup returns NULL for local resource ID 0',
                'Catalog insertion boundary captures original-built item object', 'Inherited UI/collections/transport boundaries'],
            'limitations': ['Catalog preview only; no verified placement, original templates/icons or buy/sell']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('binary'); p.add_argument('--out', required=True)
    a = p.parse_args(); result = run(a.binary)
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('ORIGINAL_SHOP_CATALOG_NAME_PRICE_PARSE_PASS', len(result['items']))
