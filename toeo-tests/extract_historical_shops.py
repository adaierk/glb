"""Extract factual, merchant-scoped stock from an archived WikiHouse shop page.

Input is a downloaded original EUC-JP page. No inferred map IDs, appearance,
coordinates, template IDs or icon IDs are promoted to verified game data.
"""
import argparse
import hashlib
import html
import json
import re
from pathlib import Path


def plain(value):
    return html.unescape(re.sub('<[^>]+>', '', value)).replace('†', '').strip()


def extract(path, url):
    raw = Path(path).read_bytes()
    text = raw.decode('euc_jp', errors='replace')
    text = text.split('<div class="span9 body">', 1)[1].split('<div id="attach">', 1)[0]
    region = area = merchant = anchor = None
    shops = []
    for match in re.finditer(r'<h([234])\b[^>]*>(.*?)</h\1>|<table\b[^>]*>(.*?)</table>', text, re.S):
        level, title, table = match.groups()
        if level:
            name = plain(title)
            a = re.search(r'class="anchor_super anchor" id="([^"]+)"', title)
            anchor = a.group(1) if a else None
            if level == '2': region = name; area = merchant = None
            elif level == '3': area = name; merchant = None
            else: merchant = name
            continue
        rows = []
        for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', table, re.S):
            cells = [plain(c) for c in re.findall(r'<t[hd]\b[^>]*>(.*?)</t[hd]>', row, re.S)]
            rows.append(cells)
        if not rows or rows[0][:2] != ['名称', '価格']:
            continue
        stock = []
        for row in rows[1:]:
            if len(row) < 2: continue
            price = row[1].replace(',', '')
            stock.append({'name': row[0], 'price_gald': int(price) if price.isdigit() else None,
                          'category': row[2] if len(row) > 2 else None,
                          'jobs': row[3] if len(row) > 3 else None,
                          'level': int(row[4]) if len(row) > 4 and row[4].isdigit() else None,
                          'native_template_id': None, 'native_icon_id': None})
        coordinate = re.search(r'X\s*[:;]\s*(\d+)\s*[,、]\s*Y\s*[:;]\s*(\d+)', merchant or '', re.I)
        source_key = anchor or f'table-{len(shops)}'
        shops.append({'key': 'wikihouse-' + source_key, 'region': region, 'area': area,
                      'merchant': merchant, 'source_xy': [int(coordinate[1]), int(coordinate[2])] if coordinate else None,
                      'coordinate_system': 'Historical Wiki X/Y; original native grid conversion unverified',
                      'native_map_id': None, 'native_entity_id': None, 'appearance': None,
                      'deployment': 'pending_map_and_coordinate_verification',
                      'source_url': url + ('#' + anchor if anchor else ''), 'stock': stock})
    return {'schema_version': 1, 'source': {'url': url, 'sha256': hashlib.sha256(raw).hexdigest(),
        'encoding': 'EUC-JP', 'recorded_at': '2026-10-09', 'version_note': 'Historical community record; beta/final server version consistency unverified'},
        'shops': shops}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('original_html'); p.add_argument('--url', required=True); p.add_argument('--out', required=True)
    a = p.parse_args(); result = extract(a.original_html, a.url)
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'shops': len(result['shops']), 'stock_rows': sum(len(x['stock']) for x in result['shops']),
                      'with_xy': sum(x['source_xy'] is not None for x in result['shops'])}))
