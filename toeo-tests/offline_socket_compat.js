'use strict';
// The original 6086e0 callback accepts only WSAEWOULDBLOCK, rejecting a
// successful synchronous localhost connection. Adapt that exact check only;
// original socket initialization and all game/protocol states still execute.
(function () {
  const a = va => Process.mainModule.base.add(va - 0x400000);
  const ws = Process.getModuleByName('ws2_32.dll');
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
  for(const [va,name] of [[0x60e6a0,'socket_init'],[0x61ba60,'world_controller_start']]) {
    Interceptor.attach(a(va), {
      onEnter(args){this.p=this.context.ecx;send({event:name+'_enter',object:this.p.toString(),args:[args[0].toString(),args[1].toString()]});},
      onLeave(ret){send({event:name+'_leave',result:ret.toInt32()});}
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
