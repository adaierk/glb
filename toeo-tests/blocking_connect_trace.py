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


if(false) { // Disable native instruction probes while diagnosing packet-related crash
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
observeNativeVA(0x6befe0,'async_frame');
observeNativeVA(0x6c0b30,'packet_dispatch');
observeNativeVA(0x619a10,'raw_receive_method');


function watchOpcodeVA(va,label) {
  try {
    const p=Process.mainModule.base.add(va-0x400000);
    let seen=0;
    Interceptor.attach(p,{onEnter(args){
      if(++seen>8)return;
      try{
        const c=this.context;
        const result={event:'OPCODE_'+label,va:va.toString(16),
           edi:c.edi.toInt32(),esi:c.esi.toInt32(),
           eax:c.eax.toString(),ebp:c.ebp.toString(),esp:c.esp.toString()};
        if(va===0x6145e7 || va===0x61462d || va===0x614673) {
          result.remaining=c.esp.add(0x18).readU32();
          try{result.headerWord4=c.ebp.add(4).readU16()}catch(e){}
        }
        emit(result);
      }catch(e){emit({event:'OPCODE_ERROR',label,error:String(e)})}
    }});
    emit({event:'OPCODE_HOOKED',label,addr:p.toString()});
  }catch(e){emit({event:'OPCODE_ATTACH_ERROR',label,error:String(e)})}
}
observeNativeVA(0x60e1e0,'message_assembler');
watchOpcodeVA(0x6145e7,'need18bytes');
watchOpcodeVA(0x61462d,'header_word');
watchOpcodeVA(0x614673,'packet_frame_length');
watchOpcodeVA(0x614f14,'insufficient_frame');


function inspectMachine(va,label){
  try{
    const target=Process.mainModule.base.add(va-0x400000);
    let hits=0;
    Interceptor.attach(target,{onEnter(args){
      ++hits;
      if(hits>23)return;
      try{
        const r=this.context;
        emit({event:'BRANCH_TRACE',label,va:va.toString(16),hit:hits,
          eip:r.eip.toString(),eax:r.eax.toString(),ecx:r.ecx.toString(),
          edx:r.edx.toString(),esi:r.esi.toString(),edi:r.edi.toString(),
          ebp:r.ebp.toString(),esp:r.esp.toString(),ret:this.returnAddress.toString()});
      }catch(e){emit({event:'BRANCH_TRACE_ERROR',label,error:String(e)})}
    }});
    emit({event:'BRANCH_ATTACH_OK',label});
  }catch(e){emit({event:'BRANCH_ATTACH_ERR',label,error:String(e)})}
}
inspectMachine(0x6143d0,'state_dispatch_enter');
inspectMachine(0x614524,'pre_receive');
inspectMachine(0x61452f,'post_receive');
inspectMachine(0x614537,'rx_has_bytes');
inspectMachine(0x6145d8,'pre_assemble');
inspectMachine(0x6145df,'post_assemble');
inspectMachine(0x6145e7,'rx_enough_data');
inspectMachine(0x614f14,'rx_need_more');
inspectMachine(0x614f8d,'rx_zero_return');
inspectMachine(0x61500c,'rx_error_return');
inspectMachine(0x60e1e0,'assembler_enter');
inspectMachine(0x6bee00,'frame_decode_enter');

}


const traceno={};
function watchNativeBranch(va,label){
  try{
    let address=Process.mainModule.base.add(va-0x400000);
    Interceptor.attach(address,{onEnter(args){
      let n=(traceno[label]||0)+1;traceno[label]=n;if(n>12)return;
      try{
        const c=this.context;
        let header='';
        try{header=Array.from(new Uint8Array(c.esi.readByteArray(48))).map(x=>x.toString(16).padStart(2,'0')).join('')}catch(e){header='unavailable'}
        emit({event:'NATIVE_LOGIN_BRANCH',label,va:va.toString(16),n,
          eax:c.eax.toString(),esi:c.esi.toString(),ecx:c.ecx.toString(),
          ebp:c.ebp.toString(),esp:c.esp.toString(),header});
      }catch(e){emit({event:'NATIVE_LOGIN_BRANCH_ERROR',label,error:String(e)})}
    }});
    emit({event:'NATIVE_LOGIN_HOOKED',label,addr:address.toString()});
  }catch(e){emit({event:'NATIVE_LOGIN_HOOK_FAIL',label,error:String(e)})}
}
watchNativeBranch(0x6148b6,'validity_opcode_range');
watchNativeBranch(0x614911,'header_rejected');
watchNativeBranch(0x61497e,'header_accepted');
watchNativeBranch(0x614a06,'handler_dispatch');

const ntCount={};
function traceNativeRoute(va,label){
  try{
    const p=Process.mainModule.base.add(va-0x400000);
    Interceptor.attach(p,{onEnter(args){
      const n=(ntCount[label]||0)+1;ntCount[label]=n;
      if(n>6)return;
      const c=this.context;
      emit({event:'TOEO_ROUTE_TRACE',label,n,ip:p.toString(),eax:c.eax.toString(),
        ecx:c.ecx.toString(),edx:c.edx.toString(),ebx:c.ebx.toString(),
        esi:c.esi.toString(),edi:c.edi.toString(),esp:c.esp.toString()});
    }});
    emit({event:'TOEO_ROUTE_HOOKED',label,addr:p.toString()});
  }catch(e){emit({event:'TOEO_ROUTE_HOOK_FAIL',label,error:String(e)})}
}
traceNativeRoute(0x608ce3,'recv_completed');
traceNativeRoute(0x608c00,'raw_socket_wrapper');
traceNativeRoute(0x619a10,'network_rx_method');
traceNativeRoute(0x6143d0,'main_packet_parser');
traceNativeRoute(0x614110,'alternate_packet_parser');
traceNativeRoute(0x615240,'second_parser');
traceNativeRoute(0x615da6,'network_frame_driver');
traceNativeRoute(0x60e1e0,'frame_assembler');
traceNativeRoute(0x60ce60,'framed_packet_scanner');
traceNativeRoute(0x60c350,'frame_type_validator');
traceNativeRoute(0x612430,'packet_processor');
traceNativeRoute(0x6bee00,'secondary_frame_decoder');
traceNativeRoute(0x6c0b30,'secondary_packet_dispatch');

const parserStats={};
function inspectOriginalParserVA(va,label){
 try{
  let p=Process.mainModule.base.add(va-0x400000);
  Interceptor.attach(p,{
    onEnter(args){
      const n=(parserStats[label]||0)+1;parserStats[label]=n;
      this.capture=n<12;
      if(!this.capture)return;
      this.labels=label;
      if(label==='native_scanner'){
        try{
          this.a0=args[0];this.a1=args[1];this.a2=args[2];this.a3=args[3];
          const d=Array.from(new Uint8Array(this.a0.readByteArray(Math.min(72,this.a1.toInt32()))));
          const ctx=this.context.ecx;
          let headerEndian=-1;try{headerEndian=ctx.add(0xac).readU32()}catch(e){}
          let maxPacket=-1;try{maxPacket=ctx.add(0x80).readU32()}catch(e){}
          emit({event:'TOEO_PARSER_ENTER',name:label,buffer:this.a0.toString(),length:this.a1.toInt32(),endian_flag:headerEndian,max_packet:maxPacket,
           head:d.map(x=>x.toString(16).padStart(2,'0')).join(''),a2:this.a2.toString(),a3:this.a3.toString()});
        }catch(e){emit({event:'TOEO_PARSER_ARG_ERR',name:label,error:String(e)})}
      }else{
        try{
          emit({event:'TOEO_PARSER_ENTER',name:label,ecx:this.context.ecx.toString(),
           esi:this.context.esi.toString(),edi:this.context.edi.toString(),
           args0:args[0].toString(),args1:args[1].toString()});
        }catch(e){emit({event:'TOEO_PARSER_ARG_ERR',name:label,error:String(e)})}
      }
    },
    onLeave(ret){
      if(!this.capture)return;
      let obj={event:'TOEO_PARSER_RETURN',name:label,result:ret.toString(),number:ret.toInt32()};
      if(label==='native_scanner')for(const k of ['a2','a3']){
        try{obj[k+'value']=this[k].readU32()}catch(e){obj[k+'value']='unavailable'}
      }
      emit(obj)
    }
  });
  emit({event:'TOEO_PARSER_HOOKED',label,at:p.toString()});
 }catch(e){emit({event:'TOEO_PARSER_HOOK_FAIL',label,error:String(e)})}
}
inspectOriginalParserVA(0x60ce60,'native_scanner');
inspectOriginalParserVA(0x60e1e0,'assembler_framed');
function onParserDecision(va,label){
 try{
 let p=Process.mainModule.base.add(va-0x400000);
 let count=0;
 Interceptor.attach(p,{onEnter(args){
  if(++count>12)return;
  const c=this.context;
  emit({event:'TOEO_DECISION',name:label,hit:count,eax:c.eax.toString(),ebp:c.ebp.toString(),
   esi:c.esi.toString(),ecx:c.ecx.toString(),edi:c.edi.toString()});
 }});
 emit({event:'TOEO_DECISION_HOOKED',label,at:p.toString()});
 }catch(e){emit({event:'TOEO_DECISION_HOOK_FAIL',label,error:String(e)})}
}
onParserDecision(0x60cfdf,'scanner_status1');
onParserDecision(0x60d0d0,'scanner_status2');
onParserDecision(0x60d0a3,'scanner_status0');
onParserDecision(0x60e2ab,'assembler_scanner_return');
onParserDecision(0x60e2b7,'assembler_maybe_complete');
onParserDecision(0x60e2cf,'assembler_partial');
onParserDecision(0x6145df,'main_assembler_return');
onParserDecision(0x6145e7,'main_frame_ready');

const statusCount={};
function trace401(va,name){
try{
  const addr=Process.mainModule.base.add(va-0x400000);
  Interceptor.attach(addr,{onEnter(args){
    const i=(statusCount[name]||0)+1;statusCount[name]=i;if(i>8)return;
    const c=this.context;
    let data={event:'TOEO_401_STATE',name,count:i,eax:c.eax.toString(),
      ebx:c.ebx.toString(),ecx:c.ecx.toString(),esi:c.esi.toString(),
      edi:c.edi.toString(),esp:c.esp.toString()};
    try{data.conn_state=c.esi.add(0x60).readU32()}catch(e){}
    try{data.callback_object=c.esi.add(0x0c).readPointer().toString()}catch(e){}
    try{data.payload=c.ebx.readByteArray(24).toString()}catch(e){}
    try{data.status=c.ebx.add(0x11).readU8()}catch(e){}
    emit(data)
  }});
  emit({event:'TOEO_401_HOOK_READY',name,at:addr.toString()});
}catch(e){emit({event:'TOEO_401_HOOK_FAILED',name,error:String(e)})}
}
trace401(0x61273c,'handler_401_start');
trace401(0x61277e,'status_check');
trace401(0x612789,'invalid_state');
trace401(0x6127b5,'callback_guard');
trace401(0x6127c0,'callback_object_present');
trace401(0x6127fd,'deliver_login_reply');
trace401(0x612987,'abort_no_callback');
trace401(0x60bd20,'original_auth_dispatch_callback');


const sessCounters={};
function traceSession(va,label){
  try{
    const p=Process.mainModule.base.add(va-0x400000);
    Interceptor.attach(p,{onEnter(args){
      const n=(sessCounters[label]||0)+1;sessCounters[label]=n;
      if(n>20)return;
      const c=this.context;
      const r={event:'TOEO_SESSION_LIFECYCLE',label,n,eip:p.toString(),ecx:c.ecx.toString(),
       esi:c.esi.toString(),edi:c.edi.toString(),ebx:c.ebx.toString(),eax:c.eax.toString()};
      try{r.owner=c.ecx.add(0xc).readPointer().toString()}catch(e){}
      try{r.registerCount=c.ecx.add(4).readU32()}catch(e){}
      try{r.registerCapacity=c.ecx.add(0x14).readU32()}catch(e){}
      try{r.conn_state=c.ecx.add(0x60).readU32()}catch(e){}
      emit(r);
    }});
    emit({event:'TOEO_SESSION_HOOK_INSTALLED',label});
  }catch(e){emit({event:'TOEO_SESSION_HOOK_ERR',label,error:String(e)})}
}
traceSession(0x617ad0,'session_register');
traceSession(0x617bf1,'session_owner_store');
traceSession(0x60bd20,'outbound_request');
traceSession(0x611a56,'outbound_general_call');
traceSession(0x615ec0,'outbound_handshake_call');
traceSession(0x6161b9,'outbound_second_handshake');
traceSession(0x61281b,'receive_402_zero_records');
traceSession(0x612869,'receive_402_validate_ok');
traceSession(0x612a4b,'receive_402_finished');
traceSession(0x61273c,'receive_401');


const connectDiag={selects:0,conn:0,getsockopt:0,getsockerror:0};
let lastWSA=null;
try{
  lastWSA=new NativeFunction(Process.getModuleByName('ws2_32.dll').getExportByName('WSAGetLastError'),'int',[]);
}catch(e){emit({event:'TOEO_SOCKET_DIAGNOSTIC_LOAD_ERR',error:String(e)})}
hook('ws2_32.dll','connect',function(a){
  this.addr=a[1];this.sock=a[0].toString();this.track=false;
  try{let port=this.addr.add(2).readU8()*256+this.addr.add(3).readU8();this.track=port===11100;
   if(this.track)emit({event:'TOEO_CONNECT_PRE',socket:this.sock,port:port,ip:[4,5,6,7].map(i=>this.addr.add(i).readU8()).join('.')});
  }catch(e){}
},function(ret){
  if(!this.track)return;
  let code=null; try{if(lastWSA)code=lastWSA()}catch(e){}
  emit({event:'TOEO_CONNECT_RETURN',socket:this.sock,result:ret.toInt32(),wsa_error:code});
});
hook('ws2_32.dll','getsockopt',function(a){
  this.sock=a[0].toString();this.level=a[1].toInt32();this.key=a[2].toInt32();this.dest=a[3];this.len=a[4];this.idx=++connectDiag.getsockopt;
},function(ret){
  if(this.idx>100)return;
  let val=null;
  try{val=this.dest.readS32()}catch(e){}
  emit({event:'TOEO_GETSOCKOPT',n:this.idx,socket:this.sock,level:this.level,name:this.key,result:ret.toInt32(),value:val});
});
hook('ws2_32.dll','select',function(a){
 this.idx=++connectDiag.selects;
 this.rd=a[1];this.wr=a[2];this.ex=a[3];
},function(ret){
 let rc=ret.toInt32();
 if(rc<=0&&this.idx>12)return;
 const count=p=>{try{return p.isNull()?null:p.readU32()}catch(e){return -1}};
 emit({event:'TOEO_SELECT_SCAN',n:this.idx,result:rc,readable:count(this.rd),writable:count(this.wr),except:count(this.ex)});
});
for(const [va,label] of [[0x615dd0,'native_send_frontend'],[0x615e25,'sender_ready'],
 [0x615e77,'sender_state_five'],[0x615ec0,'sender_build_405'],[0x6161b9,'sender_build_main'],
 [0x617ad0,'session_request_registry'],[0x617bf1,'session_owner_assignment'],
 [0x60bd20,'packet_queue_or_register'],[0x6127b5,'callback_guard'],[0x6178c0,'allocate_registration']]){
 try{
  const pos=Process.mainModule.base.add(va-0x400000);
  let n=0;
  Interceptor.attach(pos,{onEnter(args){
    if(++n>24)return;
    let c=this.context, row={event:'TOEO_SENDER_STAGE',label,n,eip:pos.toString(),caller:this.returnAddress.toString(),
        ecx:c.ecx.toString(),eax:c.eax.toString(),ebx:c.ebx.toString(),esi:c.esi.toString()};
    for(const [tag,off] of [['owner',0xc],['connstate',0x60],['flags',0xb0],['timer',0xf4],['register_count',4],['register_limit',0x14]]){
      try{row[tag]=c.ecx.add(off).readU32()}catch(e){}
    }
    emit(row)
  }});
  emit({event:'TOEO_SENDER_HOOK_READY',name:label});
 }catch(e){emit({event:'TOEO_SENDER_HOOK_FAILED',name:label,error:String(e)})}
}


const blockingConnectMode='___CONNECT_BLOCKING___';
try {
 const m=Process.getModuleByName('ws2_32.dll');
 const f=m.getExportByName('ioctlsocket');
 const io=new NativeFunction(f,'int',['pointer','ulong','pointer']);
 const api=m.getExportByName('connect');
 Interceptor.attach(api,{
  onEnter(args){
   this.track=false;this.sock=args[0];
   try{
    const sockaddr=args[1],port=sockaddr.add(2).readU8()*256+sockaddr.add(3).readU8();
    if(port!==11100)return;
    this.track=true;
    if(blockingConnectMode==='blocking'){
     const v=Memory.alloc(4);v.writeU32(0);this.blockModePtr=v;
     const rc=io(this.sock,0x8004667e,v);
     emit({event:'TOEO_BLOCKING_SOCKET_BEFORE_CONNECT',socket:this.sock.toString(),rc,mode:blockingConnectMode});
    }else{
     emit({event:'TOEO_BLOCKING_CONTROL',mode:blockingConnectMode,socket:this.sock.toString()});
    }
   }catch(e){emit({event:'TOEO_BLOCKING_CONNECT_ENTER_ERROR',error:String(e)})}
  },
  onLeave(ret){
   if(!this.track)return;
   emit({event:'TOEO_BLOCKING_CONNECT_RETURN',mode:blockingConnectMode,rawRet:ret.toInt32()});
   if(blockingConnectMode==='blocking'){
    try{
     const v=Memory.alloc(4);v.writeU32(1);const rc=io(this.sock,0x8004667e,v);
     emit({event:'TOEO_RESTORE_SOCKET_NONBLOCK',socket:this.sock.toString(),result:rc});
    }catch(e){emit({event:'TOEO_RESTORE_NONBLOCK_ERROR',error:String(e)})}
   }
  }
 });
 emit({event:'TOEO_BLOCKING_CONNECT_HOOK_INSTALLED',mode:blockingConnectMode});
}catch(e){emit({event:'TOEO_BLOCKING_CONNECT_INSTALL_ERR',error:String(e)})}

Process.setExceptionHandler(function(details){
  try {
    const c=details.context || {};
    emit({event:'NATIVE_EXCEPTION',kind:details.type,address:String(details.address),
      eip:String(c.eip),esp:String(c.esp),eax:String(c.eax),
      ebx:String(c.ebx),ecx:String(c.ecx),edx:String(c.edx),esi:String(c.esi),edi:String(c.edi)});
  } catch(e) {emit({event:'NATIVE_EXCEPTION_LOGGING_ERROR',error:String(e)});}
  return false;
});


// Trace native header parsing at the original 2006 executable virtual address.
try {
  const executable=Process.getModuleByName('ToEO_CL_trace.exe');
  const addr=executable.base.add(0x20b030);
  Interceptor.attach(addr,{
    onEnter(args){
      this.ptr=args[0];
      this.no=(sent.nativeHeader=(sent.nativeHeader||0)+1);
      if(this.no<=90){
        try {emit({event:'TOEO_HEADER_SWAP_BEFORE',i:this.no,bytes:hex(Array.from(new Uint8Array(this.ptr.readByteArray(24))))})}
        catch(e){emit({event:'TOEO_HEADER_READ_ERROR',error:String(e)})}
      }
    },
    onLeave(ret){
      if(this.no<=90){
        try {emit({event:'TOEO_HEADER_SWAP_AFTER',i:this.no,bytes:hex(Array.from(new Uint8Array(this.ptr.readByteArray(24))))})}
        catch(e){}
      }
    }
  });
  emit({event:'TOEO_HEADER_HOOK_READY',addr:addr.toString()});
}catch(e){emit({event:'TOEO_HEADER_HOOK_ERROR',error:String(e)})}

emit({event:'hook_setup_complete'});
"""
agent=agent.replace('___CONNECT_BLOCKING___',os.environ.get('TOEO_CONNECT_BLOCKING','control'))

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
    def on_detached(reason, crash):
        print('SESSION_DETACHED reason='+str(reason)+' crash='+str(crash),flush=True)
        log.write(json.dumps({'event':'SESSION_DETACHED','reason':str(reason),'crash':str(crash)},ensure_ascii=False)+'\n')
    session.on('detached',on_detached)
    script=session.create_script(agent)
    script.on('message',on_message)
    script.load()
    device.resume(pid)
    for tick in range(123):
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
