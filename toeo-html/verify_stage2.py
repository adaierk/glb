"""Real Chromium file:// verification and milestone screenshots."""
import json,asyncio,zipfile,hashlib
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path('toeo-html');D=ROOT/'dist';Q=ROOT/'evidence-stage2';Q.mkdir(parents=True,exist_ok=True)
async def main():
 errors=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  page=await browser.new_page(viewport={'width':1040,'height':870},device_scale_factor=1)
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('requestfailed',lambda r:errors.append(r.url+':'+str(r.failure)))
  external=[]
  page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) else None)
  await page.goto((D/'index.html').resolve().as_uri(),wait_until='load')
  await page.wait_for_function('window.TOEO && TOEO.ready',timeout=120000)
  await page.wait_for_timeout(500)
  assert not errors,errors
  assert not await page.evaluate('TOEO.errors')
  assert not external,external
  assert await page.evaluate("Array.from(document.getElementById('miniimg').getContext('2d').getImageData(0,0,137,128).data).filter((v,i)=>i%4===3 && v>0).length")>10000
  initial=await page.evaluate('TOEO.state')
  assert initial['grid']==[139,313] and initial['gald']==2000
  assert await page.evaluate('TOEO.walkable([139,313]) && TOEO.walkable([141,313]) && !TOEO.walkable([141,312])')
  assert await page.evaluate('JSON.stringify(TOEO.gridToPoint([139,313]))')=='[4480,5024]'
  await page.locator('#game').screenshot(path=str(Q/'01_HTML_Map.png'))
  # Walk through native diamond cells, then verify reload restores the endpoint.
  assert await page.evaluate('TOEO.go([143,313])')
  await page.wait_for_function('TOEO.state.grid[0]===143',timeout=10000)
  await page.reload(wait_until='load')
  await page.wait_for_function('TOEO.ready',timeout=120000)
  assert await page.evaluate('TOEO.state.grid')==[143,313]
  assert await page.evaluate('TOEO.speak()')
  await page.locator('#quantity').fill('2')
  await page.locator('#trade').click()
  bought=await page.evaluate('TOEO.state')
  assert bought['gald']==1280 and bought['inventory']=={'1':2}
  before=await page.evaluate('JSON.stringify(TOEO.state)')
  rejected=await page.evaluate("""() => {
    const trials=[()=>TOEO.transact(1,1.5,'buy'),()=>TOEO.transact(1,0,'buy'),()=>TOEO.transact(1,100,'buy'),()=>TOEO.transact(3,2,'buy'),()=>TOEO.transact(1,3,'sell'),()=>TOEO.validSave({...TOEO.state,grid:[141,312]}),()=>TOEO.validSave({...TOEO.state,gald:-1})];
    return trials.map(f=>{try{f();return false}catch(e){return true}})
  }""")
  assert all(rejected),rejected
  assert await page.evaluate('JSON.stringify(TOEO.state)')==before
  await page.locator('#quantity').fill('1')
  await page.locator('#selltab').click()
  await page.locator('#trade').click()
  assert await page.evaluate('TOEO.state.gald')==1460
  assert await page.evaluate('TOEO.state.inventory')=={'1':1}
  await page.locator('#game').screenshot(path=str(Q/'02_HTML_Trade.png'))
  await page.evaluate("TOEO.open('bag')")
  await page.locator('#game').screenshot(path=str(Q/'03_HTML_Inventory.png'))
  await page.evaluate("TOEO.hide();TOEO.inspect(9000,3000)")
  await page.wait_for_timeout(700)
  assert not await page.evaluate('TOEO.errors')
  await page.locator('#game').screenshot(path=str(Q/'04_HTML_Full_Map_Inspection.png'))
  # An isolated browser context checks the imported save validator and mobile layout.
  mobile=await browser.new_page(viewport={'width':390,'height':780},device_scale_factor=1)
  await mobile.goto((D/'index.html').resolve().as_uri(),wait_until='load')
  await mobile.wait_for_function('TOEO.ready',timeout=120000)
  assert await mobile.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
  await mobile.screenshot(path=str(Q/'05_HTML_Mobile.png'))
  # Stage 2 active combat: old schema saves migrate, actions consume TP/items,
  # enemy retaliation resolves, victory persists XP/currency/drop, retreat gives none.
  assert await page.evaluate("""() => {
    const old={schema:1,map:'1120108',grid:[143,313],name:'Legacy',gald:100,hp:80,tp:20,inventory:{}};
    return TOEO.validSave(old).level===1 && TOEO.validSave(old).exp===0
  }""")
  rejected_progress=await page.evaluate("""() => {
    try{TOEO.validSave({...TOEO.state,level:0});return false}catch(e){return true}
  }""")
  assert rejected_progress
  await page.evaluate("TOEO.open('system')")
  await page.locator('#battle-start').click()
  assert await page.evaluate('TOEO.battle && TOEO.battle.phase==="player" && TOEO.battle.enemy.id===1200')
  await page.locator('#game').screenshot(path=str(Q/'06_HTML_Battle.png'))
  initial_battle=await page.evaluate('TOEO.state')
  assert await page.evaluate("TOEO.battleAction('skill')")
  await page.wait_for_function('TOEO.battle && TOEO.battle.phase==="player" && TOEO.state.hp<100',timeout=10000)
  after_hit=await page.evaluate('TOEO.state')
  assert after_hit['tp']==initial_battle['tp']-8
  assert await page.evaluate("TOEO.battleAction('item')")
  await page.wait_for_function('TOEO.battle && TOEO.battle.phase==="player" && TOEO.state.hp===100 && !TOEO.state.inventory[1]',timeout=10000)
  assert await page.evaluate("TOEO.battleAction('attack')")
  await page.wait_for_function('TOEO.battle && TOEO.battle.phase==="player"',timeout=10000)
  assert await page.evaluate("TOEO.battleAction('attack')")
  await page.wait_for_function('TOEO.battle && TOEO.battle.phase==="victory"',timeout=10000)
  win=await page.evaluate('TOEO.state')
  assert win['gald']==1540 and win['exp']==25 and win['inventory']=={'1':1} and win['hp']<100,win
  await page.locator('#game').screenshot(path=str(Q/'07_HTML_Battle_Victory.png'))
  await page.reload(wait_until='load')
  await page.wait_for_function('TOEO.ready',timeout=120000)
  assert await page.evaluate('TOEO.state.gald===1540 && TOEO.state.exp===25 && TOEO.state.inventory[1]===1')
  before_retreat=await page.evaluate('JSON.stringify(TOEO.state)')
  assert await page.evaluate('TOEO.beginBattle()')
  assert await page.evaluate("TOEO.battleAction('retreat')")
  assert await page.evaluate('JSON.stringify(TOEO.state)')==before_retreat
  assert await page.evaluate('TOEO.battle===null')
  assert not await page.evaluate('TOEO.errors')
  result={'passed':True,'runtime':'Chromium file://, offline single HTML','external_requests':external,'browser_errors':errors,
   'checks':['complete native map data loads','native grid conversion','blocked terrain rejected','mouse path planner and movement','save survives reload','UI purchase and sale','insufficient funds rejected atomically','invalid and fractional quantities rejected atomically','inventory preserved after rejection','invalid saves rejected','full-map camera inspection','mobile viewport fits','schema 1 save migrates to combat progression','skill consumes TP and deals damage','enemy counterattack damages player','healing item is consumed and restores HP','victory awards currency, EXP and item','combat progression survives reload','retreat grants no rewards'],
   'initial':initial,'final':await page.evaluate('TOEO.state'),'textures_ready':await page.evaluate('TOEO.texturesReady'),
   'limitations':['Enemy model, official enemy spawn/stat data, original skill animations, plot, map transitions and equipment progression remain pending']}
  (Q/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
  await browser.close()
 # Package only actual validated output.
 with zipfile.ZipFile(ROOT/'TOEO_HTML_Stage2.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for f in D.iterdir():z.write(f,f.name)
 with zipfile.ZipFile(ROOT/'TOEO_HTML_Stage2_Screenshots.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for f in Q.iterdir():z.write(f,f.name)
 (Q/'package_sha256.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in ROOT.glob('TOEO_HTML_Stage2*.zip')},indent=2))
 print('TOEO_HTML_STAGE2_BROWSER_QA_PASS')
asyncio.run(main())

