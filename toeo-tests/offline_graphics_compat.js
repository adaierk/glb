'use strict';
// A renderer compatibility change, separate from read-only gameplay probes.
// The untouched client optionally calls ValidateDevice before every immediate
// primitive. Disable only that optional diagnostic after the real D3D9 method
// returns D3DERR_INVALIDCALL at its verified original call site. The original
// cooperative-level checks, draw calls and their HRESULTs remain unmodified.
// No actor, HP/TP, inventory or UI control values are written here.
(function () {
  const a=va=>Process.mainModule.base.add(va-0x400000);
  const flag=a(0x80b782),getter=a(0x623400);
  if(getter.readU8()!==0xa0 || getter.add(5).readU8()!==0xc3 ||
      getter.add(1).readU32()!==flag.toUInt32()) {
    throw new Error('Unexpected original renderer validation getter; compatibility refused');
  }
  const seen=new Set();let applied=false;
  Interceptor.attach(a(0x623410),{onEnter(args){
    const device=args[0];if(device.isNull())return;
    const validate=device.readPointer().add(0x118).readPointer(),key=validate.toString();
    if(seen.has(key))return;seen.add(key);
    Interceptor.attach(validate,{
      onEnter(){this.original=this.returnAddress.equals(a(0x623476));},
      onLeave(ret){
        if(!this.original || applied || ret.toUInt32()!==0x8876086c || flag.readU8()!==1)return;
        const before=flag.readU8();flag.writeU8(0);applied=true;
        send({event:'legacy_render_validation_compat_applied',validation_hresult:ret.toString(),
          flag_address:flag.toString(),before,after:flag.readU8(),
          note:'Disable optional ValidateDevice preflight only; real drawing and returned HRESULT unchanged'});
      }
    });
  }});
  send({event:'offline_graphics_compat_ready',initial_optional_validation:flag.readU8()});
})();
