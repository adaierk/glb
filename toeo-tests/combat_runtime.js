'use strict';
// v19 read-only probes. Never write state, redirect native returns or drive UI.
(function(){
 const emit=x=>send(x),address=va=>Process.mainModule.base.add(va-0x400000);
 function safely(f){try{return f();}catch(e){return {error:String(e)};}}
 let enemy=null,previous='',samples=0;
 function enemyState(){
  if(enemy===null||enemy.isNull())return null;
  const model=enemy.add(0x158).readPointer(),extension=enemy.add(0x64).readPointer();
  return {identity:[enemy.add(0x68).readU32(),enemy.add(0x6c).readU32()],
   category:enemy.add(0x70).readU32(),position:[enemy.add(12).readFloat(),enemy.add(16).readFloat()],
   world_model:model.toString(),battle_model:enemy.add(0x15c).readPointer().toString(),
   appearance:Array.from(new Uint8Array(enemy.add(0x110).readPointer().readByteArray(24))),
   extension:extension.isNull()?null:{vtable:extension.readPointer().toString(),kind:extension.add(8).readU32()},
   hp:enemy.add(0x114).readPointer().add(8).readU32()};
 }
 Interceptor.attach(address(0x51c1e0),{onEnter(args){this.keep=args[1].toUInt32()===0x72000001;},
  onLeave(ret){if(this.keep){enemy=ret;emit(safely(()=>({event:'native_local_enemy_created',actor:ret.toString(),...enemyState()})));}}});
 setInterval(()=>{const s=safely(enemyState);if(!s)return;const key=JSON.stringify(s);if(key!==previous){previous=key;emit({event:'native_local_enemy_state',...s});}},500);
 for(const [va,event] of [[0x501470,'native_enemy_model_load'],[0x4fe5c0,'native_enemy_action']]){
  Interceptor.attach(address(va),{onEnter(args){this.keep=enemy!==null && this.context.ecx.equals(enemy);this.args=[args[0].toString(),args[1].toString()];},
   onLeave(ret){if(this.keep && ++samples<=32)emit({event,result:ret.toInt32()&255,args:this.args,state:safely(enemyState)});}});
 }
 for(const [va,event] of [[0x49d2f0,'native_battle_group_created'],[0x529840,'native_battle_actor_created'],[0x430e50,'native_battle_init'],[0x431920,'native_battle_init_tick'],[0x5231b0,'native_battle_request_9f'],[0x522fd0,'native_battle_request_a8']]){
  Interceptor.attach(address(va),{onEnter(args){this.keep=++samples<=150;this.args=[args[0].toString(),args[1].toString(),args[2].toString()];if(this.keep)emit({event,object:this.context.ecx.toString(),args:this.args});},
   onLeave(ret){if(this.keep)emit({event:event+'_returned',result:ret.toString()});}});
 }
 emit({event:'combat_probe_ready',mode:'Read-only original enemy and encounter observations'});
})();
