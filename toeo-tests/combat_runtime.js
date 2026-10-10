undefined
(function(){
 const at=va=>Process.mainModule.base.add(va-0x400000);
 const safe=f=>{try{return f();}catch(e){return {error:String(e)};}};
 const snapshot=p=>({identity:[p.add(0x58).readU32(),p.add(0x5c).readU32()],
  readiness:p.add(0x84).readU32(),action:p.add(0x88).readU32(),position:[p.readFloat(),p.add(4).readFloat()],
  ability_counters:[p.add(0x70).readU32(),p.add(0x74).readU32()],ability_rows:p.add(0x80).readU32()});
 for(const [va,event] of [[0x511030,'native_battle_abilities_reset'],[0x50f7f0,'native_battle_abilities_ready']]){
  Interceptor.attach(at(va),{onEnter(){this.actor=ptr(this.context.ecx.toString());},onLeave(){send(safe(()=>({event,...snapshot(this.actor)})));}});
 }
 let controls=0;
 Interceptor.attach(at(0x52c2b2),{onEnter(){if(++controls<=8)send(safe(()=>({event:'native_battle_control_applied',mode:this.context.esi.add(0x1d0).readU32(),pending_flags:this.context.ebx.add(0x20).readU32()})));}});
 for(const [va,event] of [[0x513000,'native_battle_input_tick'],[0x522fd0,'native_battle_action_request_a8']]){
  let n=0;Interceptor.attach(at(va),{onEnter(args){if(++n<=24)send({event,sample:n,object:this.context.ecx.toString(),args:[args[0].toString(),args[1].toString(),args[2].toString()]});}});
 }
 send({event:'battle_initialization_probe_ready',mode:'Read-only original initialization and normal UI input observation'});
})();
