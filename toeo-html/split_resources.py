import json,base64
from pathlib import Path
R=Path('toeo-html/research');j=json.loads((R/'resources.json').read_text())
for f in j['files']:
 if 'data_b64' in f:
  name=Path(f['file']).name+'.b64';(R/name).write_text(f.pop('data_b64'));f['data_file']=name
for k,rows in j['bundles'].items():
 for x in rows:
  if 'png_b64' in x:x.pop('png_b64')
for k,x in j['ui'].items():
 (R/('ui_'+k+'.png')).write_bytes(base64.b64decode(x.pop('png_b64')))
(R/'index.json').write_text(json.dumps(j,indent=2))
print('SPLIT_RESOURCES',len(j['files']),len(j['ui']))
