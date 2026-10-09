'use strict';
// The original 6086e0 callback accepts only WSAEWOULDBLOCK, rejecting a
// successful synchronous localhost connection. Adapt that exact check only;
// original socket initialization and all game/protocol states still execute.
(function () {
  const a = va => Process.mainModule.base.add(va - 0x400000);
  const ws = Process.getModuleByName('ws2_32.dll');
  const peerLoopback=Memory.allocUtf8String('127.0.0.2');
  const lastError=new NativeFunction(ws.getExportByName('WSAGetLastError'),'int',[]);
  for(const name of ['bind','connect','socket','WSAEventSelect','ioctlsocket','getsockopt','setsockopt','listen','inet_addr']) {
    Interceptor.attach(ws.getExportByName(name), {
      onEnter(args){
        this.name=name;this.first=args[0].toString();this.caller=this.returnAddress.toString();
        if(name==='inet_addr' && [a(0x6191c7).toString(),a(0x608e2a).toString()].includes(this.caller) && args[0].readCString()==='0.0.0.0') {
          args[0]=peerLoopback;
          send({event:'legacy_zero_bind_address_compat',address:'127.0.0.2',caller:this.caller});
        }
        this.endpoint=null;
        if(name==='bind'||name==='connect') {
          const p=args[1];this.endpoint={family:p.readU16(),port:p.add(2).readU8()*256+p.add(3).readU8(),
            ip:[4,5,6,7].map(i=>p.add(i).readU8()).join('.')};
        }
        send({event:'os_socket_enter',name,first:this.first,caller:this.caller,endpoint:this.endpoint,args:[args[1].toString(),args[2].toString(),args[3].toString()],text:name==='inet_addr'?args[0].readCString():null});
      },
      onLeave(ret){send({event:'os_socket_return',name,result:ret.toInt32(),last_error:ret.toInt32()<0?lastError():0});}
    });
  }
  Interceptor.attach(ws.getExportByName('WSAGetLastError'), {
    onEnter() {this.legacy = this.returnAddress.equals(a(0x60873b));},
    onLeave(ret) {
      if(this.legacy) {
        const code=ret.toInt32();
        send({event:'legacy_sync_connect_check',original_error:code});
        if(code===0) {ret.replace(ptr(10035));send({event:'legacy_sync_connect_compat_applied'});}
      }
    }
  });
  for(const [va,name] of [[0x60e6a0,'socket_init'],[0x61ba60,'world_controller_start'],[0x619130,'socket_endpoint_init']]) {
    Interceptor.attach(a(va), {
      onEnter(args){this.p=this.context.ecx;send({event:name+'_enter',object:this.p.toString(),args:[args[0].toString(),args[1].toString()]});},
      onLeave(ret){send({event:name+'_leave',result:ret.toInt32(),internal_error:this.p.add(0x100).readS32()});}
    });
  }
  for(const name of ['sendto','recvfrom']) {
    Interceptor.attach(ws.getExportByName(name), {
      onEnter(args){this.p=args[1];this.n=args[2].toInt32();
        if(name==='sendto')send({event:name,bytes:this.n,hex:Array.from(new Uint8Array(this.p.readByteArray(Math.min(this.n,400)))).map(v=>v.toString(16).padStart(2,'0')).join('')});},
      onLeave(ret){if(name==='recvfrom' && ret.toInt32()>0)send({event:name,bytes:ret.toInt32()});}
    });
  }
  send({event:'offline_socket_compat_ready'});
})();
