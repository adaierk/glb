"""Extract unmodified TOEO resources for the offline HTML port."""
import os,sys,struct,json,base64,subprocess,io,hashlib,zlib
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path.cwd()/'toeo-tests'))
from decode_original_graphics import lz2_decode,argb1555_image
from legacy_graphics_assets import expand_palette_tga
OUT=Path('toeo-html/research');OUT.mkdir(parents=True,exist_ok=True)
RAW=Path(os.environ['RUNNER_TEMP'])/'TOEO_HTML_RAW'
pack=Path(os.environ['RUNNER_TEMP'])/'TOEO_ORIGINAL/client_pack.7z'
patterns=['NewComponent1/map/1120108.*','NewComponent1/map/1110101.*','NewComponent1/resource/pc1a.*','NewComponent1/resource/pc_body.cpd','NewComponent1/resource/pc_head.cpd','NewComponent1/resource/pc_hair.cpd','NewComponent1/resource/pc_parts.crs','NewComponent1/resource/nn001.*','NewComponent1/ui/*','NewComponent1/resource/pc1a_m.cpd','NewComponent1/resource/pc1a_amd.pkd','NewComponent1/resource/M_body_a_m_00.bnd','NewComponent1/resource/M_head_m_00.bnd','NewComponent1/resource/nn001_amd.pkd']
subprocess.run(['7z','x','-y','-o'+str(RAW),str(pack),*patterns],check=True,stdout=subprocess.DEVNULL)
report={'files':[],'maps':{},'bundles':{},'ui':{}}
b64=lambda x:base64.b64encode(x).decode()
for f in sorted(RAW.rglob('*')):
 if not f.is_file():continue
 d=f.read_bytes();rel=str(f.relative_to(RAW));entry={'file':rel,'size':len(d),'sha256':hashlib.sha256(d).hexdigest(),'header_hex':d[:160].hex()}
 report['files'].append(entry)
 if f.suffix in ('.mpd','.mpi','.atd','.crs','.cpd','.cpi','.pkd'):
  entry['compressed_data_file']=f.name+'.zlib.b64';(OUT/entry['compressed_data_file']).write_text(b64(zlib.compress(d)))
  if f.suffix!='.mpd' and len(d)<1000000:entry['data_b64']=b64(d)
 if f.suffix=='.mpd':
  n,m=struct.unpack_from('<II',d,24)
  offs=struct.unpack_from(f'<{n+m}I',d,32)
  entry['layers']=[{'offset':v,'words':list(struct.unpack_from('<7I',d,v)),'sample_words':list(struct.unpack_from('<32I',d,v+28))} for v in offs]
 if d[:8]==b'BNKD\x02\x00\x00\x00':
  count=struct.unpack_from('<I',d,8)[0];images=[]
  for i in range(count):
   length,offset=struct.unpack_from('<II',d,12+i*40)
   if offset==0xffffffff or offset+24>len(d) or length<24:continue
   w,h,depth,fmt,size,compression,reserved=struct.unpack_from('<HHIIIII',d,offset)
   e={'index':i,'offset':offset,'length':length,'width':w,'height':h,'depth':depth,'format':fmt,'size':size,'compression':compression}
   if (depth,fmt,compression)==(16,25,2):
    raw=lz2_decode(d[offset+24:offset+24+size],w*h*2)
    im=argb1555_image(raw,w,h);o=io.BytesIO();im.save(o,format='PNG');e['png_b64']=b64(o.getvalue())
    im.save(OUT/(f.stem+f'_{i:03}.png'))
   images.append(e)
  report['bundles'][rel]=images
 if f.suffix=='.tga':
  try:
   raw=d
   if d[1:3]==b'\x01\x01':raw=expand_palette_tga(d)[0]
   im=Image.open(io.BytesIO(raw)).convert('RGBA');o=io.BytesIO();im.save(o,format='PNG');report['ui'][f.stem]={'w':im.width,'h':im.height,'png_b64':b64(o.getvalue())}
  except Exception as err:entry['error']=str(err)
(OUT/'resources.json').write_text(json.dumps(report,separators=(',',':')),encoding='utf-8')
print('TOEO_HTML_RESOURCE_EXTRACTED',len(report['files']),len(report['bundles']),len(report['ui']))
