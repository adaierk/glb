'use strict';
// v15 diagnostic: reads original resource objects only; never calls getters or
// writes native memory. Run separately from gameplay acceptance verification.
(function () {
  const address=va=>Process.mainModule.base.add(va-0x400000);
  const hex=(p,n)=>Array.from(new Uint8Array(p.readByteArray(n))).map(x=>x.toString(16).padStart(2,'0')).join('');
  const observed=new Set(),getters=new Set();
  function safe(f){try{f();}catch(e){send({event:'resource_probe_read_error',error:String(e)});}}
  Interceptor.attach(address(0x68d190),{onEnter(args){this.manager=this.context.ecx;this.key=args[0].toUInt32();},onLeave(ret){
    if(this.key!==1 || ret.isNull())return;
    safe(()=>{
      const framework=address(0x80dbf4).readPointer();
      if(!this.manager.equals(framework.add(0x38).readPointer()))return;
      const key=ret.toString();if(observed.has(key))return;observed.add(key);
      const vt=ret.readPointer(),get=vt.add(0x48).readPointer();
      send({event:'native_template_provider',object:key,vtable:vt.toString(),object_hex:hex(ret,192),
        methods:Array.from({length:24},(_,i)=>vt.add(i*4).readPointer().toString()),getter:get.toString()});
      if(getters.has(get.toString()))return;getters.add(get.toString());
      let rows=0;
      Interceptor.attach(get,{onEnter(args){this.name=args[0].readCString();this.keep=++rows<=60;this.provider=this.context.ecx;},onLeave(value){if(this.keep)safe(()=>send({event:'native_template_block',name:this.name,
        provider:this.provider.toString(),pointer:value.toString(),hex:value.isNull()?null:hex(value,512)}));}});
    });
  }});
  let count=0;
  Interceptor.attach(address(0x46eaf0),{onEnter(args){this.type=args[0].toInt32();this.offset=args[1].toInt32();this.keep=++count<=70;},onLeave(value){if(this.keep)safe(()=>send({event:'native_template_lookup',type:this.type,offset:this.offset,pointer:value.toString(),hex:value.isNull()?null:hex(value,192)}));}});
})();
