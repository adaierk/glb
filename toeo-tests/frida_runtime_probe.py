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
  sent.windows=(sent.windows||0)+1;if(sent.windows < 40){emit({event:'CreateWindowExA',classHex:ascii(args[1]),titleHex:ascii(args[2])})}
},null);
hook('kernel32.dll','OutputDebugStringA',function(args){
  emit({event:'OutputDebugStringA',textHex:ascii(args[0])});
},null);
hook('kernel32.dll','GetPrivateProfileStringA',function(args){
  sent.profiles=(sent.profiles||0)+1;if(sent.profiles < 65){emit({event:'GetPrivateProfileStringA',sectionHex:ascii(args[0]),keyHex:ascii(args[1]),fileHex:ascii(args[5])})}
},null);
hook('kernel32.dll','GetPrivateProfileIntA',function(args){
  sent.profileint=(sent.profileint||0)+1;if(sent.profileint < 35){emit({event:'GetPrivateProfileIntA',sectionHex:ascii(args[0]),keyHex:ascii(args[1]),fileHex:ascii(args[3])})}
},null);
hook('kernel32.dll','CreateFileA',function(args){this.pathHex=ascii(args[0])},
  function(ret){sent.missing=(sent.missing||0)+1;if(ret.toInt32()===-1 && sent.missing < 100){emit({event:'CreateFileA_FAIL',pathHex:this.pathHex})}});
hook('kernel32.dll','LoadLibraryA',function(args){this.pathHex=ascii(args[0])},
  function(ret){sent.loadfail=(sent.loadfail||0)+1;if(ret.isNull() && sent.loadfail < 80){emit({event:'LoadLibraryA_FAIL',pathHex:this.pathHex})}});
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

function sampleAnsi(ptr,maxN=280){return ascii(ptr)}
function hookProfile(name, bufferIndex, pathIndex, valType){
  hook('kernel32.dll',name,function(args) {
      const f=raw(args[pathIndex],180);
      const path=f.map(x=>String.fromCharCode(x)).join('');
      if(path.toLowerCase().indexOf('server.ini')===-1&&path.toLowerCase().indexOf('deb.ini')===-1) return;
      this.show=true;
      this.section=ascii(args[0]);this.key=ascii(args[1]);this.file=ascii(args[pathIndex]);
      if(bufferIndex!==null)this.buffer=args[bufferIndex];
      this.def=(bufferIndex!==null?ascii(args[2]):null);
  },function(ret) {
      if(!this.show)return;
      emit({event:name+'_RESULT',sectionHex:this.section,keyHex:this.key,fileHex:this.file,
        defaultHex:this.def,returnedLength:ret.toInt32(),
        valueHex:this.buffer?ascii(this.buffer):null});
  });
}
hookProfile('GetPrivateProfileStringA',4,5,0);
hookProfile('GetPrivateProfileIntA',null,3,1);
hook('user32.dll','PostQuitMessage',function(args){emit({event:'PostQuitMessage',code:args[0].toInt32()})},null);
hook('user32.dll','DestroyWindow',function(args){this.hwnd=args[0].toString()},function(ret){emit({event:'DestroyWindow',hwnd:this.hwnd,result:ret.toInt32()})});
hook('ws2_32.dll','gethostbyname',function(args){this.name=ascii(args[0]);emit({event:'DNS_gethostbyname',nameHex:this.name})},function(ret){emit({event:'DNS_RESULT',nameHex:this.name,ptr:ret.toString()})});
hook('ws2_32.dll','getaddrinfo',function(args){this.name=ascii(args[0]);this.service=ascii(args[1]);emit({event:'DNS_getaddrinfo',hostHex:this.name,serviceHex:this.service})},function(ret){emit({event:'DNS_ADDRINFO_RESULT',hostHex:this.name,code:ret.toInt32()})});
hook('ws2_32.dll','connect',function(args){
  try {
    this.family=args[1].readU16();
    const dat=[];
    for(let i=0;i<16;i++)dat.push(args[1].add(i).readU8());
    this.dst=hex(dat);
    this.port=dat[2]*256+dat[3];
    this.ip=dat.slice(4,8).join('.');
    emit({event:'TCP_CONNECT',family:this.family,addr:this.ip,port:this.port,raw:this.dst});
    if(this.family===2 && this.port===11100){
      try{
        args[1].add(4).writeByteArray([127,0,0,1]);
        emit({event:'TOEO_OFFLINE_LOGIN_REDIRECT',original:this.ip,port:this.port,destination:'127.0.0.1'});
      }catch(e){emit({event:'TOEO_REDIRECT_ERROR',error:String(e)})}
    }
  }catch(e){emit({event:'TCP_CONNECT_err',error:String(e)})}
},function(ret){emit({event:'TCP_CONNECT_RESULT',host:this.ip,port:this.port,returnVal:ret.toInt32()})});
hook('ws2_32.dll','send',function(args){const n=args[2].toInt32();const seq=(sent.send=(sent.send||0)+1);const caller=this.returnAddress.toString();if(seq<50){let h='';try{h=Array.from(new Uint8Array(args[1].readByteArray(Math.min(500,n)))).map(x=>x.toString(16).padStart(2,'0')).join('')}catch(e){}emit({event:'send',size:n,hex:h,caller})}},null);
hook('ws2_32.dll','recv',function(args){this.buffer=args[1];this.reqLen=args[2].toInt32();this.seq=(sent.recv=(sent.recv||0)+1);this.caller=this.returnAddress.toString()},function(ret){const n=ret.toInt32();if(n>0 || this.seq<7){let h='';try{if(n>0)h=Array.from(new Uint8Array(this.buffer.readByteArray(Math.min(500,n)))).map(x=>x.toString(16).padStart(2,'0')).join('')}catch(e){}emit({event:'recv',requestLen:this.reqLen,result:n,hex:h,caller:this.caller})}});
hook('kernel32.dll','CreateProcessA',function(args){emit({event:'CreateProcessA',appHex:ascii(args[0]),cmdHex:ascii(args[1])})},function(ret){emit({event:'CreateProcessA_RESULT',success:ret.toInt32()})});
hook('kernel32.dll','LoadLibraryW',function(args){this.name=args[0].isNull()?'':args[0].readUtf16String()},function(ret){if(ret.isNull())emit({event:'LoadLibraryW_FAILED',name:this.name})});
hook('kernel32.dll','GetFileAttributesA',function(args){this.name=ascii(args[0])},function(ret){if(ret.toInt32()===-1&&((sent.attr=(sent.attr||0)+1)<40))emit({event:'GetFileAttributesA_FAIL',pathHex:this.name})});


const counters={};
function observeNativeVA(va,label){
  try{
    const m=Process.mainModule;
    const p=m.base.add(va-0x400000);
    Interceptor.attach(p,{
      onEnter(args){this.ecx=this.context.ecx.toString();this.first=args[0].toString();this.callsite=this.returnAddress.toString();},
      onLeave(ret){const n=(counters[label]||0)+1;counters[label]=n;
        if(n<=15)emit({event:'NATIVE_'+label,entryVA:va.toString(16),count:n,ecx:this.ecx,argument0:this.first,caller:this.callsite,result:ret.toInt32()});}
    });
    emit({event:'native_hook_success',function:label,actual:p.toString()});
  }catch(e){emit({event:'native_hook_error',function:label,error:String(e)})}
}
observeNativeVA(0x6bee00,'frame_decode');
observeNativeVA(0x6bf000,'async_frame');
observeNativeVA(0x6c0b30,'packet_dispatch');
observeNativeVA(0x619a10,'raw_receive_method');

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
    for tick in range(150):
        time.sleep(1)
        if tick == 34:
            try:
                import ctypes
                u=ctypes.windll.user32
                u.SetCursorPos(408,447)
                u.mouse_event(0x0002,0,0,0,0)
                time.sleep(0.12)
                u.mouse_event(0x0004,0,0,0,0)
                print("CLICKED original スタート button at screen (408,447)",flush=True)
            except Exception as e: print("Click error",repr(e),flush=True)
        if tick == 45:
            try:
                import ctypes
                u=ctypes.windll.user32
                u.SetCursorPos(218,534)
                u.mouse_event(0x0002,0,0,0,0)
                time.sleep(0.12)
                u.mouse_event(0x0004,0,0,0,0)
                print("CLICKED original 同意します agreement button at screen (218,534)",flush=True)
            except Exception as e: print("Agreement click error",repr(e),flush=True)
        if tick in [78,82]:
            try:
                import ctypes
                u=ctypes.windll.user32
                x,y=((360,299) if tick==78 else (340,391))
                u.SetCursorPos(x,y)
                u.mouse_event(0x0002,0,0,0,0)
                time.sleep(0.13)
                u.mouse_event(0x0004,0,0,0,0)
                print(f"CLICK world list or select button: tick={tick}, coords=({x},{y})",flush=True)
            except Exception as e: print("World select error",repr(e),flush=True)
        if tick in [92,96,100]:
            try:
                import ctypes
                u=ctypes.windll.user32
                def click(x,y):
                    u.SetCursorPos(x,y)
                    u.mouse_event(0x0002,0,0,0,0)
                    time.sleep(0.11)
                    u.mouse_event(0x0004,0,0,0,0)
                def type_text(value):
                    for letter in value:
                        vk=ord(letter.upper())
                        u.keybd_event(vk,0,0,0)
                        u.keybd_event(vk,0,0x0002,0)
                        time.sleep(0.055)
                if tick==92:
                    click(380,290)
                    type_text('archive001')
                    print("Entered fictitious offline research ID",flush=True)
                elif tick==96:
                    click(380,336)
                    type_text('local123')
                    print("Entered fictitious offline-only test password",flush=True)
                else:
                    click(315,405)
                    print("Clicked original game's ログイン button with NONREAL test credentials",flush=True)
            except Exception as e: print("Login test UI error",repr(e),flush=True)
        if tick in [2,6,15,28,35,40,45,46,48,51,59,68,75,79,83,88,93,97,101,107,115,127,143]:
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
