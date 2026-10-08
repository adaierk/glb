import frida
import os
import json
import time
import sys
import traceback
from pathlib import Path
from PIL import ImageGrab

game=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
out.mkdir(parents=True,exist_ok=True)
os.chdir(game.parent)
log=open(out/'frida_runtime.jsonl','w',encoding='utf-8',buffering=1)

agent=r"""
const sent={};
function emit(x){try{send(x)}catch(e){}}
function raw(p,maxN=500){
  if(p.isNull())return [];
  const a=[];
  for(let i=0;i<maxN;i++){
    try{const c=p.add(i).readU8();if(c===0)break;a.push(c)}catch(e){break}
  }
  return a;
}
function hex(a){return a.map(x=>x.toString(16).padStart(2,'0')).join('')}
function ascii(p){return hex(raw(p,350))}
function hook(lib,name,enter,leave){
  try{
    const mod=Process.getModuleByName(lib);
    const addr=mod.getExportByName(name);
    if(!addr)throw new Error('No address');
    Interceptor.attach(addr,{
      onEnter(args){if(enter)try{enter.call(this,args)}catch(e){emit({event:'onEnterErr',name,error:String(e)})}},
      onLeave(ret){if(leave)try{leave.call(this,ret)}catch(e){emit({event:'onLeaveErr',name,error:String(e)})}}
    });
    emit({event:'hooked',name,lib,addr:addr.toString()});
  }catch(e){emit({event:'hookError',name,lib,error:String(e)})}
}
hook('user32.dll','MessageBoxA',function(args){
  emit({event:'MessageBoxA',captionHex:ascii(args[2]),messageHex:ascii(args[1]),flags:args[3].toString()});
},null);
hook('user32.dll','MessageBoxW',function(args){
  emit({event:'MessageBoxW',caption:args[2].isNull()?'':args[2].readUtf16String(),message:args[1].isNull()?'':args[1].readUtf16String(),flags:args[3].toString()});
},null);
hook('user32.dll','CreateWindowExA',function(args){
  if((sent.windows||0)++ < 40){emit({event:'CreateWindowExA',classHex:ascii(args[1]),titleHex:ascii(args[2])})}
},null);
hook('kernel32.dll','OutputDebugStringA',function(args){
  emit({event:'OutputDebugStringA',textHex:ascii(args[0])});
},null);
hook('kernel32.dll','GetPrivateProfileStringA',function(args){
  if((sent.profiles||0)++ < 65){emit({event:'GetPrivateProfileStringA',sectionHex:ascii(args[0]),keyHex:ascii(args[1]),fileHex:ascii(args[5])})}
},null);
hook('kernel32.dll','GetPrivateProfileIntA',function(args){
  if((sent.profileint||0)++ < 35){emit({event:'GetPrivateProfileIntA',sectionHex:ascii(args[0]),keyHex:ascii(args[1]),fileHex:ascii(args[3])})}
},null);
hook('kernel32.dll','CreateFileA',function(args){this.pathHex=ascii(args[0])},
  function(ret){if(ret.toInt32()===-1 && (sent.missing||0)++ < 100){emit({event:'CreateFileA_FAIL',pathHex:this.pathHex})}});
hook('kernel32.dll','LoadLibraryA',function(args){this.pathHex=ascii(args[0])},
  function(ret){if(ret.isNull() && (sent.loadfail||0)++ < 80){emit({event:'LoadLibraryA_FAIL',pathHex:this.pathHex})}});
hook('kernel32.dll','ExitProcess',function(args){emit({event:'ExitProcess',exitCode:args[0].toInt32()})},null);
hook('d3d9.dll','Direct3DCreate9',function(args){this.sdk=args[0].toInt32()},
  function(ret) {
    emit({event:'Direct3DCreate9',sdkVersion:this.sdk,returned:ret.toString()});
    if(ret.isNull())return;
    try{
      const vtbl=ret.readPointer();
      const method=vtbl.add(Process.pointerSize*16).readPointer();
      Interceptor.attach(method,{
        onEnter(args) {
          this.adapter=args[1].toInt32();
          this.deviceType=args[2].toInt32();
          this.flags=args[4].toInt32();
        },
        onLeave(ret){
          emit({event:'IDirect3D9_CreateDevice',adapter:this.adapter,deviceType:this.deviceType,flags:this.flags,hresult:ret.toString()});
        }
      });
      emit({event:'hooked_CreateDevice',ptr:method.toString()});
    }catch(e){emit({event:'CreateDeviceHookErr',error:String(e)})}
  });
emit({event:'hook_setup_complete'});
"""
def parse_hex(d):
    if not isinstance(d,str): return d
    try:
        raw=bytes.fromhex(d)
        return {'japanese':raw.decode('cp932','replace'),'ansi':raw.decode('cp1252','replace'),'bytes':len(raw)}
    except Exception as e:
        return {'hex':d,'exception':repr(e)}
def on_message(message,data):
    item=message.get('payload',message) if message.get('type')=='send' else {'error':message}
    for key in list(item):
        if key.endswith('Hex'): item[key.replace('Hex','Decoded')]=parse_hex(item[key])
    log.write(json.dumps(item,ensure_ascii=False,default=str)+'\n')
    kind=item.get('event','?')
    if kind not in ('hooked','CreateWindowExA','GetPrivateProfileStringA','GetPrivateProfileIntA') or kind in ('MessageBoxA','MessageBoxW'):
        print(str(item)[:1300],flush=True)

try:
    device=frida.get_local_device()
    pid=device.spawn([str(game)])
    print("Spawned PID:",pid,flush=True)
    session=device.attach(pid)
    script=session.create_script(agent)
    script.on('message',on_message)
    script.load()
    device.resume(pid)
    for tick in range(14):
        time.sleep(1)
        if tick in [2,6]:
            try:
                shot=out/f'real_screen_at_{tick+1}s.png'
                ImageGrab.grab().save(str(shot))
                print('Captured '+str(shot),flush=True)
            except Exception as e: print('Screenshot failed',str(e),flush=True)
    try: device.kill(pid)
    except Exception as e: print("kill:",e,flush=True)
except Exception as e:
    print('FRIDA_ERROR '+repr(e),flush=True)
    traceback.print_exc()
finally:
    log.close()
