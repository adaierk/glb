"""Read preserved ICND/BNKD graphics for resource identification.

CNLzComp2 is translated from original 5F9880, and output is cross-checked
separately against unchanged x86 code. Asset pixels are decoded, not redrawn.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def lz2_decode(source, maximum):
    result = bytearray(); cursor = 0; flags = 0; remaining = 0
    def bit():
        nonlocal cursor, flags, remaining
        if not remaining:
            if cursor >= len(source): raise ValueError('Truncated LZ2 flags')
            flags = source[cursor]; cursor += 1; remaining = 8
        value = bool(flags & 128); flags = (flags << 1) & 255; remaining -= 1
        return value
    while True:
        if not bit():
            if cursor >= len(source): raise ValueError('Truncated LZ2 literal')
            result.append(source[cursor]); cursor += 1
        else:
            small = bit()
            if cursor + 2 > len(source): raise ValueError('Truncated LZ2 reference')
            first, second = source[cursor:cursor+2]; cursor += 2
            if small:
                distance, count = first, second + 3
            else:
                code = first * 256 + second
                if code == 0: return bytes(result)
                distance, count = code >> 4, (code & 15) + 3
            if distance < 1 or distance > len(result): raise ValueError('Invalid LZ2 distance')
            for _ in range(count): result.append(result[-distance])
        if len(result) > maximum: raise ValueError('LZ2 output exceeds declared buffer')


def argb1555_image(data, width, height):
    from PIL import Image
    if len(data) != width * height * 2: raise ValueError('Unexpected native pixel length')
    values = struct.unpack(f'<{width*height}H', data)
    image = Image.new('RGBA', (width, height))
    image.putdata([(((v>>10)&31)*255//31, ((v>>5)&31)*255//31, (v&31)*255//31, 255 if v&0x8000 else 0) for v in values])
    return image


def first_bnd_image(path):
    data = Path(path).read_bytes()
    if data[:8] != b'BNKD\x02\x00\x00\x00': raise ValueError('Expected preserved BNKD v2')
    length, offset = struct.unpack_from('<II', data, 12)
    width, height, depth, fmt, size, compression, reserved = struct.unpack_from('<HHIIIII', data, offset)
    if (depth, fmt, compression) != (16, 25, 2): raise ValueError('Unsupported preserved graphics format')
    if size + 24 != length: raise ValueError('BNKD image bounds mismatch')
    pixels = lz2_decode(data[offset+24:offset+24+size], width*height*2)
    return argb1555_image(pixels,width,height), {'source':str(path), 'sha256':hashlib.sha256(data).hexdigest(),
        'width':width,'height':height,'format':'A1R5G5B5','pixel_sha256':hashlib.sha256(pixels).hexdigest()}


if __name__ == '__main__':
    from PIL import Image, ImageDraw
    p=argparse.ArgumentParser();p.add_argument('minimap_directory');p.add_argument('--out',required=True);a=p.parse_args()
    output=Path(a.out);output.mkdir(parents=True,exist_ok=True);records=[];groups={}
    for source in sorted(Path(a.minimap_directory).glob('*.bnd')):
        image,meta=first_bnd_image(source);image.save(output/(source.stem+'.png'));records.append(meta)
        groups.setdefault(source.stem[:3],[]).append((source.stem,image))
    for group,items in groups.items():
        atlas=Image.new('RGB',(6*160,((len(items)+5)//6)*180),(34,34,34));draw=ImageDraw.Draw(atlas)
        for index,(name,img) in enumerate(items):
            x=index%6*160;y=index//6*180;small=img.resize((156,156));atlas.paste(small,(x,y),small);draw.text((x+4,y+158),name,fill='white')
        atlas.save(output/('atlas-'+group+'.png'))
    (output/'manifest.json').write_text(json.dumps(records,indent=2));print('PRESERVED_MINIMAPS_DECODED',len(records))
