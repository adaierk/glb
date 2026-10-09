'use strict';
// Optional receive scheduling compatibility probe. Calls the original worker
// on the game's controller thread; never assigns session or game state.
(function () {
  const a=va=>Process.mainModule.base.add(va-0x400000);
  const connections=[];
  const pump=new NativeFunction(a(0x615d60),'int',['pointer','int'],'thiscall');
  Interceptor.attach(a(0x60e6a0),{
    onEnter(){this.p=this.context.ecx;},
    onLeave(ret){if(ret.toInt32()===1)connections.push(this.p);}
  });
  let active=false,count=0;
  Interceptor.attach(a(0x61d9e0),{onLeave(){
    if(active)return;active=true;
    try {
      for(const p of connections)if(p.add(0x60).readU32()===1) {
        const result=pump(p,0);
        if(++count<12)send({event:'original_gui_receive_pump',result,connection:p.toString()});
      }
    }finally{active=false;}
  }});
})();
