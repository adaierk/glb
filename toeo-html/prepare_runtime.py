"""Prepare native sprite palettes and map geometry for the HTML stage."""
import os,sys,struct,json,base64,subprocess,io,re,zlib
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path.cwd()/'toeo-tests'))
from decode_original_graphics import lz2_decode,argb1555_image
from decode_client_tables import decrypt_blocks
R=Path('toeo-html/research');RAW=Path(os.environ['RUNNER_TEMP'])/'TOEO_HTML_RAW'
subprocess.run(['7z','x','-y','-o'+str(RAW),str(Path(os.environ['RUNNER_TEMP'])/'TOEO_ORIGINAL/client_pack.7z'),
'DefaultComponent/ToEO_CL.dat','NewComponent1/resource/M_body_a_m_00.bnd','NewComponent1/resource/M_head_m_00.bnd',
'NewComponent1/resource/pc1a_amd.pkd','NewComponent1/resource/pc1_clt.pkd','NewComponent1/resource/nn001.bnd'],check=True,stdout=subprocess.DEVNULL)
binary=(RAW/'DefaultComponent/ToEO_CL.dat').read_bytes()
keys=sorted(set(re.findall(rb'[a-zA-Z][a-zA-Z0-9 _.-]{2,30}text',binary)))
(R/'original_text_keys.json').write_text(json.dumps([k.decode() for k in keys],indent=2))
for name in ('M_body_a_m_00','M_head_m_00','nn001'):
 f=RAW/'NewComponent1/resource'/f'{name}.bnd'
 if not f.exists():continue
 d=f.read_bytes();n=struct.unpack_from('<I',d,8)[0]
 for i in range(n):
  length,off=struct.unpack_from('<II',d,12+i*40);w,h,depth,fmt,size,compression,reserved=struct.unpack_from('<HHIIIII',d,off)
  if depth==8 and fmt==21 and compression==2:
   palette=d[off+24:off+1048];indexes=lz2_decode(d[off+1048:off+1048+size],w*h)
   colors=[(palette[j+2],palette[j+1],palette[j],palette[j+3]) for j in range(0,1024,4)]
   image=Image.new('RGBA',(w,h));image.putdata([colors[x] for x in indexes])
  elif depth==16 and fmt==25 and compression==2:
   image=argb1555_image(lz2_decode(d[off+24:off+24+size],w*h*2),w,h)
  else:raise ValueError((name,depth,fmt,compression))
  image.save(R/f'{name}_{i:03}.png')
pk=(RAW/'NewComponent1/resource/pc1a_amd.pkd').read_bytes();count,pos=struct.unpack_from('<II',pk,12)
decoded=None
for key in keys:
 if b'pk' not in key:continue
 try:
  plain=bytearray(pk);off=pos
  for j in range(count):
   size=struct.unpack_from('<I',pk,off)[0];off+=4
   plain[off:off+size]=decrypt_blocks(pk[off:off+size],key);off+=size
  if b'm_body' in plain and b'.amd' in plain:decoded=plain;break
 except Exception:pass
if decoded:
 n,start=struct.unpack_from('<II',pk,28);rows=[]
 for j in range(n):
  nameptr,off,size=struct.unpack_from('<III',pk,start+j*32)
  name=bytes(decoded[nameptr:]).split(b'\\0',1)[0].decode('cp932',errors='replace')
  # Split by zero byte without source string escaping.
  name=bytes(decoded[nameptr:]).split(bytes(1),1)[0].decode('cp932',errors='replace')
  rows.append({'name':name,'offset':off,'size':size})
  if name in ('m_body.amd','m_head00.amd','m_head01.amd'):
   (R/(name+'.b64')).write_text(base64.b64encode(pk[off:off+size]).decode())
 (R/'pc1a_amd_index.json').write_text(json.dumps({'key':key.decode(),'rows':rows},indent=2))
# Preserve native layers as compact data for the complete 14400 x 10240 map.
mpd=zlib.decompress(base64.b64decode((R/'1120108.mpd.zlib.b64').read_text()))
mpi=zlib.decompress(base64.b64decode((R/'1120108.mpi.zlib.b64').read_text()))
layers,extra=struct.unpack_from('<II',mpd,24);offs=struct.unpack_from(f'<{layers+extra}I',mpd,32)
ground=[];placements=[];nav=None
for off in offs:
 kind,flags,tile,w,h,a,b=struct.unpack_from('<7I',mpd,off);values=struct.unpack_from(f'<{w*h}I',mpd,off+28)
 if kind==0:ground.append({'flags':flags,'tiles_b64':base64.b64encode(struct.pack(f'<{len(values)}H',*[65535 if x==0xffffffff else x for x in values])).decode()})
 elif kind==1:placements=[{'x':j%w,'y':j//w,'id':v} for j,v in enumerate(values) if v!=0xffffffff]
 elif kind==1200:nav=list(values)
n,offset=struct.unpack_from('<II',mpi,16);tiles=[]
for j in range(n):
 bank,uv,tag,aux,blend,alpha,a,b=struct.unpack_from('<8I',mpi,offset+j*32)
 tiles.append([bank,uv&65535,uv>>16,alpha,blend])
objects=[]
object_count=struct.unpack_from('<I',mpi,24)[0]
for j in range(object_count):
 off=struct.unpack_from('<I',mpi,32+j*4)[0]
 version,layers,x,y,w,h=struct.unpack_from('<6i',mpi,off);parts=[]
 for li in range(layers):
  po=off+struct.unpack_from('<I',mpi,off+24+li*4)[0]
  kind,tile,pw,ph,origin=struct.unpack_from('<5I',mpi,po)
  records=[list(struct.unpack_from('<5I',mpi,po+20+r*20)) for r in range(pw*ph)]
  parts.append({'kind':kind,'w':pw,'h':ph,'ox':origin&65535,'oy':origin>>16,'cells':records})
 objects.append({'id':j,'x':x,'y':y,'w':w,'h':h,'parts':parts})
doc={'map':'1120108','width':225,'height':320,'pixel_width':14400,'pixel_height':10240,'tile_w':64,'tile_h':32,'ground':ground,'tiles':tiles,'placements':placements,'objects':objects,'nav':nav}
encoded=zlib.compress(json.dumps(doc,separators=(',',':')).encode(),9)
(R/'map_runtime.zlib.b64').write_text(base64.b64encode(encoded).decode())
print('NATIVE_HTML_RUNTIME_DATA',len(encoded),len(placements),len(objects))
# Render bounded native-pixel scene to check placement before UI work.
sx,sy,ww,hh=3456,4288,2048,1536
scene=Image.new('RGBA',(ww,hh),(0,0,0,255));cache={}
def draw_tile(dst,ident,x,y,alpha=255):
 if not 0<=ident<len(tiles):return
 bank,tx,ty,ta,blend=tiles[ident]
 if bank not in cache:cache[bank]=Image.open(R/f'1120108_{bank:03}.png').convert('RGBA')
 im=cache[bank].crop((tx,ty,tx+64,ty+32))
 if alpha!=255:im.putalpha(im.getchannel('A').point(lambda a:a*alpha//255))
 dst.alpha_composite(im,(x,y))
for layer in ground:
 values=struct.unpack(f'<{225*320}H',base64.b64decode(layer['tiles_b64']))
 for y in range(sy//32,(sy+hh)//32):
  for x in range(sx//64,(sx+ww)//64):draw_tile(scene,values[y*225+x],x*64-sx,y*32-sy)
for place in sorted(placements,key=lambda p:p['y']):
 if not sx-1024<place['x']*64<sx+ww+1024 or not sy-1024<place['y']*32<sy+hh+1024:continue
 obj=objects[place['id']]
 for part in obj['parts']:
  for k,row in enumerate(part['cells']):
   draw_tile(scene,row[0],(place['x']+k%part['w']-part['ox'])*64-sx,(place['y']+k//part['w']-part['oy'])*32-sy,row[2])
scene.save(R/'native_map_scene.png')
scene.crop((624,436,1424,1036)).save(R/'native_map_viewport.png')

# Read original color lookup package without guessing its key.
pk=(RAW/'NewComponent1/resource/pc1_clt.pkd').read_bytes();count,pos=struct.unpack_from('<II',pk,12)
plain=bytearray(pk);off=pos
for j in range(count):
 size=struct.unpack_from('<I',pk,off)[0];off+=4
 plain[off:off+size]=decrypt_blocks(pk[off:off+size],b'pkd text');off+=size
n,start=struct.unpack_from('<II',pk,28);colors=[]
wanted={'skin_00.clt','hair_00.clt','eye_00.clt','head_m_00.clt','body_a_m_A_00.clt','clothes_a_m_A_00.clt','gloves_a_m_A_00.clt','shoes_a_m_A_00.clt'}
for j in range(n):
 nameptr,off,size=struct.unpack_from('<III',pk,start+j*32)
 name=bytes(plain[nameptr:]).split(bytes(1),1)[0].decode('cp932')
 if name in wanted:colors.append({'name':name,'data_b64':base64.b64encode(pk[off:off+size]).decode(),'header_hex':pk[off:off+min(size,300)].hex()})
(R/'original_color_lookups.json').write_text(json.dumps(colors,indent=2))
