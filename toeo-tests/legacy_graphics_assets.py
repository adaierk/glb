"""Losslessly expand four palette TGAs in an isolated native runtime.

Preserved client/assets stay unchanged; drawing remains entirely native.
"""
import hashlib,json,os,shutil,struct
from pathlib import Path

KNOWN_PALETTES={
 'ui/image/statusbar.tga':'e4411dde62a6266993358123341c77608fb338efac2afe8112a835d6b6a7c295',
 'ui/image/statusbar2.tga':'19a6998cf42879149be41280fde7734747e418a26dcc37cd4655c6df1a1847d5',
 'ui/image/statusbar3.tga':'25de2dedec1aff42229e3501d6a8b3c0b3557a8322802fa190664e5bc3893850',
 'resource/battlefont.tga':'46e6069913f02b4a4f51b4a7576e0492d214c36fb1788ca2e415176f08a64d59'}

def sha(data):return hashlib.sha256(data).hexdigest()

def expand_palette_tga(data):
 if len(data)<18:raise ValueError('Truncated original TGA header')
 h=list(struct.unpack('<BBBHHBHHHHBB',data[:18]))
 ident,cmap,kind,first,count,depth,_,_,width,height,bpp,descriptor=h
 if (cmap,kind,depth,bpp)!=(1,1,32,8) or not 0<count<=256 or not 0<width*height<=16777216:
  raise ValueError('Expected bounded uncompressed 8-bit TGA with a 32-bit palette')
 start=18+ident;end=start+count*4;size=width*height
 if len(data)!=end+size:raise ValueError('Unexpected original TGA payload size')
 palette=[data[start+4*i:start+4*i+4] for i in range(count)];indices=data[end:]
 if any(index<first or index>=first+count for index in indices):raise ValueError('TGA index outside palette')
 pixels=b''.join(palette[index-first] for index in indices)
 h[1]=0;h[2]=2;h[3]=h[4]=h[5]=0;h[10]=32;h[11]=(descriptor&0x30)|8
 converted=struct.pack('<BBBHHBHHHHBB',*h)+data[18:start]+pixels
 return converted,{'width':width,'height':height,'bgra_pixels_sha256':sha(pixels),
  'pixel_count':size,'alpha_preserved':True,'origin_preserved':True}

def prepare_render_client(original,runtime,manifest_path):
 original=Path(original).resolve();runtime=Path(runtime).resolve();manifest_path=Path(manifest_path)
 if runtime==original or original/'data'==runtime or original/'data' in runtime.parents:
  raise ValueError('Runtime must be separate from the original data directory')
 converted=[]
 for rel,expected in KNOWN_PALETTES.items():
  data=(original/'data'/rel).read_bytes()
  if sha(data)!=expected:raise ValueError('Original palette asset hash mismatch: '+rel)
  expanded,details=expand_palette_tga(data)
  converted.append((rel,expanded,{'file':rel,'original_sha256':expected,'converted_sha256':sha(expanded),**details}))
 runtime.mkdir(parents=True,exist_ok=True)
 for source in original.iterdir():
  if source.is_file() and not source.name.startswith('ToEO_CL_local'):
   shutil.copy2(source,runtime/source.name)
 for source in (original/'data').rglob('*'):
  if not source.is_file():continue
  target=runtime/'data'/source.relative_to(original/'data');target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists() and os.path.samefile(source,target):continue
  target.unlink(missing_ok=True)
  try:os.link(source,target)
  except OSError:shutil.copy2(source,target)
 for rel,expanded,details in converted:
  target=runtime/'data'/rel;temp=target.with_name(target.name+'.toeo_palette_tmp')
  # Atomic replacement breaks the hard link; never write through it.
  temp.write_bytes(expanded);os.replace(temp,target)
  assert sha((original/'data'/rel).read_bytes())==details['original_sha256']
 for directory in ('log','userdata'):(runtime/directory).mkdir(exist_ok=True)
 manifest={'version':'v16','original_directory':str(original),'runtime_directory':str(runtime),
  'original_assets_unchanged':True,'changes':'Four palette TGAs expanded losslessly in isolated runtime only',
  'files':[row for _,_,row in converted]}
 manifest_path.parent.mkdir(parents=True,exist_ok=True)
 manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 return runtime
