from pathlib import Path

p=Path("toeo-html/app.html")
s=p.read_text(encoding="utf-8")
def once(old,new,label):
    global s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected one match, got {n}")
    s=s.replace(old,new,1)

once("@media(max-width:650px){.wrap{padding:5px}.heading{font-size:10px}.mobile{display:flex;justify-content:center;gap:7px;margin-top:8px}.mobile button{padding:9px 16px}.footer{font-size:10px}}",
"""@media(max-width:650px){.wrap{padding:5px}.heading{font-size:10px}.mobile{display:flex;justify-content:center;gap:7px;margin-top:8px}.mobile button{padding:9px 16px}.footer{font-size:10px}.battle-actions{left:10px;right:10px;gap:3px;padding:4px}.battle-actions button{min-width:78px;padding:2px 5px;font-size:11px}.battle-actions button.retreat{min-width:58px}.battle-message{left:20px;right:20px}.battle-card{width:170px}}
.battle-screen{display:none;position:absolute;inset:0;z-index:8;overflow:hidden;background:#18262d}.battle-screen.open{display:block}#battlefield{width:800px;height:600px;image-rendering:pixelated}.battle-title{position:absolute;left:214px;top:9px;width:372px;text-align:center;padding:2px 5px;height:25px;z-index:1}.battle-card{position:absolute;top:42px;width:190px;min-height:55px;padding:4px 7px;z-index:1}.battle-card.enemy{right:13px}.battle-card.hero{left:13px}.battle-card .bar{position:relative;left:auto;right:auto;bottom:auto;margin-top:3px;height:10px}.battle-card .bar i{transition:width .18s}.battle-name{display:flex;justify-content:space-between;font-weight:bold;margin-bottom:2px}.battle-message{position:absolute;left:139px;right:139px;bottom:112px;min-height:42px;padding:6px 10px;line-height:1.55;z-index:1}.battle-actions{position:absolute;left:115px;right:115px;bottom:10px;height:91px;padding:7px;display:flex;justify-content:center;align-items:center;gap:8px;z-index:1}.battle-actions button{min-width:105px;min-height:46px;font-weight:bold}.battle-actions button span{display:block;font-size:10px;font-weight:normal;color:#62583f;margin-top:2px}.battle-actions button.retreat{min-width:72px}.battle-hint{position:absolute;right:8px;top:104px;color:#f8f2d0;text-shadow:1px 1px #253138;font-size:10px;z-index:1}""","battle css")
once("阶段 1 · 河口地图 / 交易 / 存档","阶段 2 · 河口地图 / 战斗 / 存档","stage header")
once('<div class="hud panel"><div class="title" id="player-name">Archive</div><div class="hudline">HP<strong id="hp">100</strong><div class="bar"><i id="hpbar"></i></div></div><div class="hudline tp">TP<strong id="tp">30</strong><div class="bar"><i id="tpbar"></i></div></div><div class="hudline exp">EXP<strong>0%</strong><div class="bar"><i style="width:0"></i></div></div><div class="lv">Lv.1</div></div>',
'<div class="hud panel"><div class="title" id="player-name">Archive</div><div class="hudline">HP<strong id="hp">100</strong><div class="bar"><i id="hpbar"></i></div></div><div class="hudline tp">TP<strong id="tp">30</strong><div class="bar"><i id="tpbar"></i></div></div><div class="hudline exp">EXP<strong id="expvalue">0%</strong><div class="bar"><i id="expbar" style="width:0"></i></div></div><div class="lv" id="level">Lv.1</div></div>',"experience HUD")
once('<div class="dialog panel" id="system"><div class="title">システム<button class="close" data-close>×</button></div><div class="content about"><p>离线存档会自动保存位置、金钱与背包。</p><div class="trade-controls"><button class="gold" id="export">导出存档</button><button class="gold" id="import">导入存档</button><input hidden id="savefile" type="file" accept=".json"></div><p><button class="gold" id="inspect">自由查看地图</button><button class="gold" id="center">返回角色</button></p><p><button class="gold" id="aboutbutton">本阶段说明</button></p><p id="save-status" class="note"></p></div></div>',
'<div class="dialog panel" id="system"><div class="title">システム<button class="close" data-close>×</button></div><div class="content about"><p>离线存档会自动保存位置、金钱、背包与战斗成长。</p><p><button class="gold" id="battle-start">开始战斗系统测试</button> <span class="note">测试遭遇：客户端敌人资源记录 ID 1200</span></p><div class="trade-controls"><button class="gold" id="export">导出存档</button><button class="gold" id="import">导入存档</button><input hidden id="savefile" type="file" accept=".json"></div><p><button class="gold" id="inspect">自由查看地图</button><button class="gold" id="center">返回角色</button></p><p><button class="gold" id="aboutbutton">本阶段说明</button></p><p id="save-status" class="note"></p></div></div>',"system menu")
once('<div class="loading panel" id="loading">','''<div class="battle-screen" id="battle-screen" aria-label="单机战斗测试">
<canvas id="battlefield" width="800" height="600"></canvas>
<div class="battle-title panel">战斗系统测试 · 客户端敌人资源 ID 1200</div>
<div class="battle-card hero panel"><div class="battle-name"><span id="battle-player-name">Archive</span><span>HP <b id="battle-player-hp">100 / 100</b></span></div><div class="bar"><i id="battle-player-bar"></i></div><div class="note" id="battle-player-tp">TP 30 / 30</div></div>
<div class="battle-card enemy panel"><div class="battle-name"><span id="battle-enemy-name">SLIME · 1200</span><span>HP <b id="battle-enemy-hp">52 / 52</b></span></div><div class="bar"><i id="battle-enemy-bar"></i></div><div class="note">本地遭遇测试数值</div></div>
<div class="battle-hint">Z 攻击　1 技能　2 道具　3 防御　Esc 撤退</div>
<div class="battle-message panel" id="battle-message">遭遇记录测试。请选择行动；战斗数值为本地验证数据。</div>
<div class="battle-actions panel" id="battle-actions">
<button class="gold" data-battle-action="attack">攻击<span>Z · 普通攻击</span></button>
<button class="gold" data-battle-action="skill">技能<span>1 · 消耗 TP 8</span></button>
<button class="gold" data-battle-action="item">道具<span>2 · 使用背包回复品</span></button>
<button class="gold" data-battle-action="guard">防御<span>3 · 减少下次伤害</span></button>
<button class="gold retreat" id="battle-exit">撤退<span>Esc</span></button>
</div></div>
<div class="loading panel" id="loading">''',"battle screen")
once('let state={schema:1,map:"1120108",grid:[139,313],name:"Archive",gald:2000,hp:100,tp:30,inventory:{}}',
'let state={schema:2,map:"1120108",grid:[139,313],name:"Archive",gald:2000,hp:100,tp:30,level:1,exp:0,inventory:{}}',"initial player state")
old='function validSave(s){if(!s||s.schema!==1||s.map!=="1120108"||!Array.isArray(s.grid)||s.grid.length!==2||!walkable(s.grid)||!Number.isSafeInteger(s.gald)||s.gald<0||s.gald>2147483647||!Number.isInteger(s.hp)||s.hp<0||s.hp>100||!Number.isInteger(s.tp)||s.tp<0||s.tp>30||typeof s.name!=="string"||s.name.length>16||!s.inventory||typeof s.inventory!=="object"||Array.isArray(s.inventory))throw Error("存档数据不符合本版本格式");for(const[k,n]of Object.entries(s.inventory))if(!STOCK.some(i=>String(i.id)===k)||!Number.isInteger(n)||n<0||n>MAX)throw Error("存档中有无效道具");return {schema:1,map:"1120108",grid:[...s.grid],name:s.name,gald:s.gald,hp:s.hp,tp:s.tp,inventory:{...s.inventory}}}'
new='function validSave(s){if(!s||![1,2].includes(s.schema)||s.map!=="1120108"||!Array.isArray(s.grid)||s.grid.length!==2||!walkable(s.grid)||!Number.isSafeInteger(s.gald)||s.gald<0||s.gald>2147483647||!Number.isInteger(s.hp)||s.hp<0||s.hp>100||!Number.isInteger(s.tp)||s.tp<0||s.tp>30||typeof s.name!=="string"||s.name.length>16||!s.inventory||typeof s.inventory!=="object"||Array.isArray(s.inventory))throw Error("存档数据不符合本版本格式");const level=s.level??1,exp=s.exp??0;if(!Number.isInteger(level)||level<1||level>99||!Number.isInteger(exp)||exp<0||exp>=100)throw Error("存档中的成长数据无效");for(const[k,n]of Object.entries(s.inventory))if(!STOCK.some(i=>String(i.id)===k)||!Number.isInteger(n)||n<0||n>MAX)throw Error("存档中有无效道具");return {schema:2,map:"1120108",grid:[...s.grid],name:s.name,gald:s.gald,hp:s.hp,tp:s.tp,level,exp,inventory:{...s.inventory}}}'
once(old,new,"save migration")
once('$("player-name").textContent=state.name;$("hp").textContent=state.hp;$("tp").textContent=state.tp;',
'$("player-name").textContent=state.name;$("hp").textContent=state.hp;$("tp").textContent=state.tp;$("level").textContent="Lv."+state.level;$("expvalue").textContent=state.exp+"%";$("expbar").style.width=state.exp+"%";',"level HUD update")
once('function key(e){if(/INPUT|SELECT|TEXTAREA/.test(e.target?.tagName||""))return;const k=e.key.toLowerCase();if(k==="escape"){e.preventDefault();if(document.querySelector(".dialog.open"))hide();else open("system");return}if(k==="i")return open("bag");',
'function key(e){if(/INPUT|SELECT|TEXTAREA/.test(e.target?.tagName||""))return;const k=e.key.toLowerCase();if(k==="escape"){e.preventDefault();if(battle){battleAction("retreat");return}if(document.querySelector(".dialog.open"))hide();else open("system");return}if(battle){const action={z:"attack","1":"skill","2":"item","3":"guard"}[k];if(action)battleAction(action);return}if(k==="i")return open("bag");',"combat keyboard routing")
once('window.TOEO={get state(){return JSON.parse(JSON.stringify(state))},',
'window.TOEO={get state(){return JSON.parse(JSON.stringify(state))},get battle(){return battle?JSON.parse(JSON.stringify(battle)):null},beginBattle,battleAction,',"battle test hooks")
once('document.addEventListener("keydown",key);document.querySelectorAll("[data-key]").forEach',
'document.addEventListener("keydown",key);$("battle-start").onclick=beginBattle;$("battle-exit").onclick=()=>battleAction("retreat");document.querySelectorAll("[data-battle-action]").forEach(b=>b.onclick=()=>battleAction(b.dataset.battleAction));document.querySelectorAll("[data-key]").forEach',"battle controls")
once('const canvas=$("world"),ctx=canvas.getContext("2d",{alpha:false}),textureCache=new Map();',
'const canvas=$("world"),ctx=canvas.getContext("2d",{alpha:false}),textureCache=new Map(),battleCanvas=$("battlefield"),battleCtx=battleCanvas.getContext("2d");let battle=null,battleTimer=null;',"battle canvas state")
battle=r"""
function renderBattle(){
 if(!battle){$("battle-screen").classList.remove("open");return}
 $("battle-screen").classList.add("open");battleCtx.imageSmoothingEnabled=false;
 battleCtx.drawImage(canvas,0,0,W,H);
 battleCtx.fillStyle="rgba(12,24,29,.55)";battleCtx.fillRect(0,0,W,H);
 const floor=battleCtx.createLinearGradient(0,350,0,560);floor.addColorStop(0,"#766c4e");floor.addColorStop(1,"#3a4943");
 battleCtx.fillStyle=floor;battleCtx.beginPath();battleCtx.moveTo(0,365);battleCtx.lineTo(800,350);battleCtx.lineTo(800,600);battleCtx.lineTo(0,600);battleCtx.closePath();battleCtx.fill();
 battleCtx.strokeStyle="#c6b57b66";battleCtx.lineWidth=2;for(let i=0;i<6;i++){const y=450+i*26;battleCtx.beginPath();battleCtx.moveTo(0,y);battleCtx.lineTo(800,y-18);battleCtx.stroke()}
 battleCtx.fillStyle="#16211d66";battleCtx.beginPath();battleCtx.ellipse(220,423,43,11,0,0,Math.PI*2);battleCtx.fill();
 if(images.avatar)battleCtx.drawImage(images.avatar,0,0,64,100,160,230,120,188);
 battleCtx.fillStyle="#16211d66";battleCtx.beginPath();battleCtx.ellipse(614,428,67,14,0,0,Math.PI*2);battleCtx.fill();
 const jelly=battleCtx.createRadialGradient(590,365,8,615,393,68);jelly.addColorStop(0,"#dcff9c");jelly.addColorStop(.48,"#8fd554");jelly.addColorStop(1,"#397f48");
 battleCtx.fillStyle=jelly;battleCtx.beginPath();battleCtx.moveTo(550,413);battleCtx.quadraticCurveTo(560,350,603,342);battleCtx.quadraticCurveTo(647,339,675,411);battleCtx.quadraticCurveTo(624,440,550,413);battleCtx.fill();
 battleCtx.strokeStyle="#e5ffb0";battleCtx.lineWidth=3;battleCtx.beginPath();battleCtx.ellipse(605,366,20,7,-.25,Math.PI,Math.PI*2);battleCtx.stroke();
 battleCtx.fillStyle="#18352a";battleCtx.beginPath();battleCtx.ellipse(595,390,4,7,0,0,Math.PI*2);battleCtx.ellipse(634,389,4,7,0,0,Math.PI*2);battleCtx.fill();
 battleCtx.strokeStyle="#315b39";battleCtx.lineWidth=2;battleCtx.beginPath();battleCtx.arc(615,404,9,.2,Math.PI-.2);battleCtx.stroke();
 battleCtx.font="bold 13px 'MS Gothic','Microsoft YaHei',sans-serif";battleCtx.textAlign="center";battleCtx.fillStyle="#f9f0c6";battleCtx.strokeStyle="#1b3028";battleCtx.lineWidth=3;battleCtx.strokeText("SLIME · ID 1200",614,328);battleCtx.fillText("SLIME · ID 1200",614,328);
 $("battle-player-name").textContent=state.name;$("battle-player-hp").textContent=state.hp+" / 100";$("battle-player-bar").style.width=state.hp+"%";$("battle-player-bar").style.background=state.hp<30?"#d54c3f":"#20acd0";$("battle-player-tp").textContent="TP "+state.tp+" / 30";
 $("battle-enemy-hp").textContent=Math.max(0,battle.enemy.hp)+" / "+battle.enemy.maxHp;$("battle-enemy-bar").style.width=Math.max(0,battle.enemy.hp/battle.enemy.maxHp*100)+"%";$("battle-message").textContent=battle.message;
 const done=["victory","defeat"].includes(battle.phase);document.querySelectorAll("[data-battle-action]").forEach(b=>b.disabled=battle.phase!=="player");
 $("battle-exit").innerHTML=done?'返回地图<span>关闭战斗</span>':'撤退<span>Esc · 无奖励</span>';
}
function beginBattle(){
 if(battle)return false;if(state.hp<=0){state.hp=50;persist();status()}
 path=[];motion=null;inspectMode=false;hide();
 battle={enemy:{name:"SLIME",id:1200,hp:52,maxHp:52},phase:"player",turn:0,guard:false,message:"遭遇测试开始。普通攻击、技能、道具与防御均可操作。"};
 renderBattle();log("单机战斗测试开始：敌人资源记录 ID 1200。");return true
}
function closeBattle(){
 if(battleTimer){clearTimeout(battleTimer);battleTimer=null}
 if(!battle)return false;
 const phase=battle.phase;battle=null;$("battle-screen").classList.remove("open");path=[];status();
 if(phase==="victory")log("战斗胜利，奖励已保存。");else if(phase==="defeat")log("战斗结束：已保存当前 HP。");else log("战斗已撤退，未获得奖励。");
 return true
}
function winBattle(){
 battle.phase="victory";state.gald=Math.min(2147483647,state.gald+80);state.exp+=25;
 while(state.exp>=100){state.exp-=100;state.level=Math.min(99,state.level+1)}
 const drop=STOCK.find(i=>i.name==="レモングミ")||STOCK[0];if(drop)state.inventory[drop.id]=Math.min(MAX,(state.inventory[drop.id]||0)+1);
 battle.message="胜利！获得 80 Gald、25 EXP 和 1 个回复道具。奖励为离线系统测试数据。";
 persist();status();renderBag();renderBattle();log("胜利：+80 Gald、+25 EXP、回复道具 ×1。");
}
function enemyBattleTurn(){
 battleTimer=null;if(!battle||battle.phase!=="enemy")return;
 const damage=battle.guard?3:9;battle.guard=false;state.hp=Math.max(0,state.hp-damage);battle.turn++;
 if(state.hp===0){battle.phase="defeat";battle.message="战斗测试失败。当前 HP 已保存；可以使用背包道具恢复。"}
 else{battle.phase="player";battle.message=battle.lastAction+"；敌人反击，造成 "+damage+" 点伤害。轮到你行动。"}
 persist();status();renderBattle();
}
function battleAction(action){
 if(!battle)return false;
 if(action==="retreat"){closeBattle();return true}
 if(battle.phase!=="player")return false;
 let damage=0;
 if(action==="attack"){damage=18;battle.lastAction="普通攻击命中，造成 "+damage+" 点伤害"}
 else if(action==="skill"){if(state.tp<8){battle.message="TP 不足，需要 8 TP。";renderBattle();return false}state.tp-=8;damage=30;battle.lastAction="技能命中，造成 "+damage+" 点伤害"}
 else if(action==="guard"){battle.guard=true;battle.lastAction="进入防御姿态；下一次反击伤害降低"}
 else if(action==="item"){
  const item=STOCK.find(i=>(state.inventory[i.id]||0)>0&&i.effect);
  if(!item){battle.message="背包中没有可用回复道具。";renderBattle();return false}
  const oldHp=state.hp,oldTp=state.tp;state.hp=Math.min(100,state.hp+item.effect[0]);state.tp=Math.min(30,state.tp+item.effect[1]);state.inventory[item.id]--;
  if(!state.inventory[item.id])delete state.inventory[item.id];
  battle.lastAction=item.name+"：HP "+(state.hp-oldHp)+" / TP "+(state.tp-oldTp);renderBag()
 }else return false;
 battle.enemy.hp=Math.max(0,battle.enemy.hp-damage);
 if(battle.enemy.hp===0){winBattle();return true}
 battle.phase="enemy";battle.message=battle.lastAction+"。";persist();status();renderBattle();
 battleTimer=setTimeout(enemyBattleTurn,450);return true
}
"""
once('function key(e){',battle+'\nfunction key(e){',"combat runtime")
once('<p>角色首帧使用原版分层图像的默认调色板；自定义颜色、行走动画、商人外观与 UI 窗口布局正在移植。原版剧情、战斗规则、其他地图切换尚未完成。</p>',
'<p>角色首帧使用原版分层图像的默认调色板；自定义颜色、行走动画、商人外观与 UI 窗口布局正在移植。战斗入口现可验证行动、敌方反击、道具、经验与奖励；敌人模型、原版招式动画及正式投放数值尚未接入。</p>',"progress notes")
once('<kbd>Esc</kbd> 菜单。解压后直接打开 index.html。',
'<kbd>Esc</kbd> 菜单；战斗测试按 <kbd>Z</kbd> 攻击、<kbd>1</kbd> 技能、<kbd>2</kbd> 道具、<kbd>3</kbd> 防御。解压后直接打开 index.html。',"controls help")
p.write_text(s,encoding="utf-8")
print("TOEO_STAGE2_SOURCE_READY",len(s))
