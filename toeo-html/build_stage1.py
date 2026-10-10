import json,base64,shutil,zipfile,io,hashlib
from pathlib import Path
from PIL import Image
R=Path('toeo-html/research');D=Path('toeo-html/dist');D.mkdir(parents=True,exist_ok=True)
uri=lambda p:'data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()
assets=json.loads(Path('toeo-html/source_assets.json').read_text());assets['ui']={};assets.setdefault('items',{});assets['tiles']={}
for name in ('icon_01','icon_02','icon_03','icon_04','itemslot'):
 assets['ui'][name]=uri(R/('ui_'+name+'.png'))
sheet=Image.open(R/'ui_ui_004.png').convert('RGBA');paper=sheet.crop((11,11,299,49));o=io.BytesIO();paper.save(o,format='PNG');assets['paper']='data:image/png;base64,'+base64.b64encode(o.getvalue()).decode()
empty=Image.new('RGBA',(32,32));o=io.BytesIO();empty.save(o,format='PNG');assets['empty']='data:image/png;base64,'+base64.b64encode(o.getvalue()).decode()
for n in range(605):assets['tiles'][n]=uri(R/f'1120108_{n:03}.png')
# Component geometry will replace this temporary first atlas frame.
body=Image.open(R/'M_body_a_m_00_default.png').convert('RGBA');head=Image.open(R/'M_head_m_00_default.png').convert('RGBA')
avatar=Image.new('RGBA',(64,100));avatar.alpha_composite(body.crop((0,0,48,72)),(8,28));avatar.alpha_composite(head.crop((0,0,64,64)),(0,0));o=io.BytesIO();avatar.save(o,format='PNG')
assets['avatar']='data:image/png;base64,'+base64.b64encode(o.getvalue()).decode();assets['avatarRect']=[0,0,64,100]
catalog=json.loads(Path('toeo-tests/historical_shops.json').read_text());stock=next(s['stock'] for s in catalog['shops'] if s['key']=='wikihouse-u392bcdb')
recovery={'レモングミ':[300,0],'ミックスグミ':[50,20],'パイングミ':[0,100],'マグログミ':[500,0]}
for i,item in enumerate(stock):item['id']=i+1;item['effect']=recovery.get(item['name'])
app=Path('toeo-html/app.html').read_text().replace('__ASSETS__',json.dumps(assets,ensure_ascii=False,separators=(',',':'))).replace('__STOCK__',json.dumps(stock,ensure_ascii=False,separators=(',',':'))).replace('__MAP_B64__',(R/'map_runtime.zlib.b64').read_text()).replace('__UZIP__',Path('toeo-html/vendor/UZIP.js').read_text())
(D/'index.html').write_text(app,encoding='utf-8')
readme='''永恒传说OL HTML 离线移植 · 阶段 1
解压后直接用 Chrome 或 Edge 打开 index.html，无需启动服务器或联网。
操作：鼠标点击码头移动，点击行商人买卖；方向键移动；E 交谈；I 背包；M 小地图；Esc 菜单。
已接入：原版 1120108 完整地图贴图及物件布局、码头寻路、历史行商人商品价格、购买出售、背包、位置和金钱存档、导入导出。
当前限制：移动暂按原图类型 3 的码头区域开放；角色使用原版分层图像首帧和默认颜色，自定义颜色、行走动画及 UI 完整布局仍在移植。
剧情、战斗规则、其他地图之间的切换尚未完成。初始 HP 100 / TP 30 / 2,000 Gald、99 堆叠和半价回收是离线测试设置。
本阶段未使用小地图替代游戏场景，也未使用旧客户端截图作为 HTML 运行截图。
源代码分支：toeo-html-offline-20261010
'''
(D/'说明.txt').write_text(readme,encoding='utf-8')
shutil.copyfile('toeo-html/vendor/LICENSE.txt',D/'UZIP_License.txt')
print('TOEO_HTML_BUILT',len(app.encode()),hashlib.sha256(app.encode()).hexdigest())
