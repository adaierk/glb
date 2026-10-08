import frida, sys, os, time, json, traceback
from pathlib import Path
from PIL import ImageGrab
game=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
out.mkdir(parents=True,exist_ok=True)
os.chdir(game.parent)
log=(out/'minimal_trace.jsonl').open('w',encoding='utf-8',buffering=1)
agent=r"""
function report(x){try{send(x)}catch(e){}}
function hook(name,cb){
  try{
    const p=Process.getModuleByName("ws2_32.dll").getExportByName(name);
    Interceptor.attach(p,{onEnter:cb});
    report({event:"hooked",name:name,at:p.toString()});
  }catch(e){report({event:"hook_fail",name:name,error:String(e)})}
}
hook("connect",function(args){
 try{
  const p=args[1],fam=p.readU16(),a=[];
  for(let i=0;i<8;i++)a.push(p.add(i).readU8());
  const port=a[2]*256+a[3],ip=a.slice(4,8).join(".");
  report({event:"CONNECT_ORIGINAL",ip:ip,port:port});
  if(fam===2 && port===11100){
   p.add(4).writeByteArray([127,0,0,1]);
   report({event:"CONNECT_ISOLATED",ip:"127.0.0.1",port:11100});
  }
 }catch(e){report({event:"connect_error",error:String(e)})}
});
Process.setExceptionHandler(function(e){
 report({event:"CLIENT_EXCEPTION",type:e.type,address:String(e.address),eip:String(e.context.eip)});
 return false;
});
report({event:"READY"});
"""
def note(obj):
 log.write(json.dumps(obj,ensure_ascii=False)+"\n")
 print(json.dumps(obj,ensure_ascii=False)[:1800],flush=True)
def handler(msg,data):
 if msg.get('type')=='send':note(msg.get('payload'))
 else:note({'event':'SCRIPT_ERROR','payload':msg})
def click(x,y):
 import ctypes
 u=ctypes.windll.user32
 u.SetCursorPos(x,y);u.mouse_event(2,0,0,0,0);time.sleep(.11);u.mouse_event(4,0,0,0,0)
def typetext(s):
 import ctypes
 u=ctypes.windll.user32
 for ch in s:
  k=ord(ch.upper())
  u.keybd_event(k,0,0,0);u.keybd_event(k,0,2,0);time.sleep(.04)
def detached(reason,crash):
 note({"event":"DETACHED","reason":str(reason),"crash":str(crash)})
try:
 device=frida.get_local_device()
 pid=device.spawn([str(game)])
 note({'event':'PROCESS_SPAWNED','pid':pid})
 session=device.attach(pid)
 session.on('detached',detached)
 script=session.create_script(agent)
 script.on('message',handler)
 script.load()
 device.resume(pid)
 for tick in range(116):
  time.sleep(1)
  try:
   if tick==34:click(408,447);note({'event':'CLICK_START','tick':tick})
   if tick==45:click(218,534);note({'event':'CLICK_AGREE','tick':tick})
   if tick==78:click(360,299);note({'event':'WORLD_ROW','tick':tick})
   if tick==82:click(340,391);note({'event':'WORLD_SELECT','tick':tick})
   if tick==92:click(380,290);typetext('archive001');note({'event':'FAKE_ID_ENTERED'})
   if tick==96:click(380,336);typetext('local123');note({'event':'FAKE_PASSWORD_ENTERED'})
   if tick==100:click(315,405);note({'event':'LOGIN_PRESSED'})
   if tick in (89,102,106,111):
    p=out/f'real_t_{tick+1}.png'
    ImageGrab.grab().save(p)
    note({'event':'SCREEN_CAPTURED','path':str(p)})
  except Exception as e:note({'event':'UI_ERROR','error':repr(e)})
 try:device.kill(pid)
 except Exception:pass
except Exception as e:
 note({'event':'ERROR','error':repr(e),'traceback':traceback.format_exc()})
finally:log.close()
