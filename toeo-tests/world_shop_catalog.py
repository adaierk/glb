"""Original D6 catalog records and provenance-aware historical stock.

Historical shop coordinates are kept separate from native placements until map
and coordinate identities are verified. Preview goods carry local catalog IDs;
original template/icon IDs have not yet been recovered.
"""
import json
import struct
from pathlib import Path
from world_map_packets import record

PREVIEW_SOURCE_KEY = 'wikihouse-u392bcdb'


def historical_shops():
    return json.loads(Path(__file__).with_name('historical_shops.json').read_text(encoding='utf-8'))


def historical_stock(key):
    return next(shop for shop in historical_shops()['shops'] if shop['key'] == key)


def verified_map_shops(map_id):
    """Never place a historical merchant using a guessed map or coordinate."""
    return [shop for shop in historical_shops()['shops']
            if shop['native_map_id'] == map_id and shop['deployment'] == 'verified_native_placement']


def name_record(name):
    text = name.encode('utf-16le') + b'\0\0'
    result = record(0x9b, (8 + len(text) + 3) & ~3)
    result[8:8+len(text)] = text
    return bytes(result)


def catalog_records(stock):
    result = bytearray()
    for index, item in enumerate(stock):
        price = item['price_gald']
        if not isinstance(price, int) or not 0 <= price <= 0x7fffffff:
            raise ValueError('Catalog price has not been verified')
        result.extend(record(0x9a, 4))
        result.extend(name_record(item['name']))
        item_record = record(0x9d, 0x44)
        # Native 59A800..59A852 feeds 51D780. These are local catalog-row IDs,
        # never presented as the recovered official item template/instance IDs.
        struct.pack_into('<IIIII', item_record, 0x14, index+1, 0, 0, 0, 1)
        struct.pack_into('<hhh', item_record, 0x28, 0, 0, 0)
        struct.pack_into('<IIII', item_record, 0x34, 0, 0, 0, 0)
        result.extend(item_record)
        price_record = record(0x9e, 16)
        struct.pack_into('<III', price_record, 4, price, 0, 0)
        result.extend(price_record)
        result.extend(record(0x9f, 4))
    result.extend(bytes(4))
    return bytes(result)
