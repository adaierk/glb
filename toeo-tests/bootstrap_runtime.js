'use strict';
// Observes the real Windows client. No writes to native session/registry memory.
const emit = x => send(x);
const base = Process.mainModule.base;
const address = va => base.add(va - 0x400000);
function snapshot(p) {
  try {
    const own = p.add(0xc).readPointer();
    return {connection:p.toString(), owner:own.toString(),
      registered:p.add(4).readU32(), state:p.add(0x60).readU32(),
      target_state:p.add(0xb0).readU32(), endian_flag:p.add(0xac).readU32(),
      own_uid:p.add(0x38).readU32(),
      member_adapter:own.isNull()?null:own.add(0x34).readPointer().toString()};
  } catch (e) { return {error:String(e)}; }
}
function observe(va, name, maximum) {
  let count = 0;
  Interceptor.attach(address(va), {
    onEnter(args) {
      this.keep=++count<=maximum;
      if(!this.keep)return;
      this.self=this.context.ecx;
      this.before=snapshot(this.self);
      this.fields={event:name, count, caller:this.returnAddress.toString()};
      if(name==='packet_dispatch') {
        this.fields.opcode=args[0].add(6).readU16();
        this.fields.length=args[0].add(4).readU16();
      }
      emit({...this.fields,phase:'enter',...this.before});
    },
    onLeave(ret) {
      if(!this.keep)return;
      const after=snapshot(this.self);
      emit({...this.fields,phase:'leave',result:ret.toInt32(),...after});
      if(this.before.owner==='0x0' && after.owner && after.owner!=='0x0')
        emit({event:'OWN_SESSION_CREATED_NATIVE',...after});
    }
  });
}
observe(0x612430,'packet_dispatch',30);
observe(0x617ad0,'user_registration',30);
observe(0x615dd0,'connection_handshake',100);
// Account-login state is separate from the 0x0401/0x0402 network-user protocol.
let loginCount=0;
Interceptor.attach(address(0x61d9e0), {
  onEnter() {
    this.self=this.context.ecx;this.keep=++loginCount<=30;
    if(this.keep)emit({event:'ACCOUNT_LOGIN_HANDLER_ENTER',
      status:this.self.add(0x18).readS32(),stage:this.self.add(0x118).readS32()});
  },
  onLeave() {
    if(this.keep)emit({event:'ACCOUNT_LOGIN_HANDLER_LEAVE',
      status:this.self.add(0x18).readS32(),stage:this.self.add(0x118).readS32()});
  }
});
const ws=Process.getModuleByName('ws2_32.dll');
const loopback=Memory.allocUtf8String('127.0.0.1');
Interceptor.attach(ws.getExportByName('gethostbyname'), {
  onEnter(args) {
    emit({event:'offline_dns',original:args[0].readCString()});
    args[0]=loopback;
  }
});
Interceptor.attach(ws.getExportByName('connect'), {
  onEnter(args) {
    const p=args[1];
    const family=p.readU16();
    const port=p.add(2).readU8()*256+p.add(3).readU8();
    if(family===2)p.add(4).writeByteArray([127,0,0,1]);
    else if(family===23)p.add(8).writeByteArray([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1]);
    else throw new Error('Unsupported socket address family '+family);
    // Keep established test ports. Send other destinations to a closed local port.
    if(![45000,11100,11101,45001,45002].includes(port))p.add(2).writeByteArray([0,9]);
    emit({event:'offline_connect',port,destination:'127.0.0.1'});
  }
});
for(const name of ['send','recv']) {
  Interceptor.attach(ws.getExportByName(name), {
    onEnter(args) {
      this.buffer=args[1];this.length=args[2].toInt32();
      if(name==='send')emit({event:'client_send',bytes:this.length,
        hex:Array.from(new Uint8Array(this.buffer.readByteArray(this.length)))
          .map(x=>x.toString(16).padStart(2,'0')).join('')});
    },
    onLeave(ret) {
      if(name==='recv' && ret.toInt32()>0)emit({event:'client_recv',bytes:ret.toInt32()});
    }
  });
}
Process.setExceptionHandler(details=>{
  emit({event:'native_exception',type:details.type,address:String(details.address),stack:Thread.backtrace(details.context,Backtracer.ACCURATE).map(String)});
  return false;
});
emit({event:'runtime_probe_ready',image_base:base.toString()});
