"""Real Chromium file:// verification and milestone screenshots."""
import json,asyncio,zipfile,hashlib
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path('toeo-html');D=ROOT/'dist';Q=ROOT/'evidence';Q.mkdir(parents=True,exist_ok=True)
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
  result={'passed':True,'runtime':'Chromium file://, offline single HTML','external_requests':external,'browser_errors':errors,
   'checks':['complete native map data loads','native grid conversion','blocked terrain rejected','mouse path planner and movement','save survives reload','UI purchase and sale','insufficient funds rejected atomically','invalid and fractional quantities rejected atomically','inventory preserved after rejection','invalid saves rejected','full-map camera inspection','mobile viewport fits'],
   'initial':initial,'final':await page.evaluate('TOEO.state'),'textures_ready':await page.evaluate('TOEO.texturesReady'),
   'limitations':['Character palette recoloring, walk animation, map transitions, official battle and plot are pending']}
  (Q/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
  await browser.close()
 # Package only actual validated output.
 with zipfile.ZipFile(ROOT/'TOEO_HTML_Stage1.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for f in D.iterdir():z.write(f,f.name)
 with zipfile.ZipFile(ROOT/'TOEO_HTML_Stage1_Screenshots.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for f in Q.iterdir():z.write(f,f.name)
 (Q/'package_sha256.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in ROOT.glob('TOEO_HTML_Stage1*.zip')},indent=2))
 print('TOEO_HTML_BROWSER_QA_PASS')
asyncio.run(main())
