'use strict';
// v19 read-only probes. Never write state, redirect native returns or drive UI.
(function(){
 const emit=x=>send(x),address=va=>Process.mainModule.base.add(va-0x400000);
 function safely(f){try{return f();}catch(e){return {error:String(e)};}}
 let enemy=null,previous='',samples=0,battleSamples=0,enemyLoad=0;
 function enemyState(){
  if(enemy===null||enemy.isNull())return null;
  const model=enemy.add(0x158).readPointer(),extension=enemy.add(0x64).readPointer();
  return {identity:[enemy.add(0x68).readU32(),enemy.add(0x6c).readU32()],
   flags:enemy.add(0xa8).readU32(),load_requested:enemy.add(0x154).readU8(),load_done:enemy.add(0x155).readU8(),
   category:enemy.add(0x70).readU32(),position:[enemy.add(12).readFloat(),enemy.add(16).readFloat()],
   world_model:model.toString(),battle_model:enemy.add(0x15c).readPointer().toString(),
   appearance:Array.from(new Uint8Array(enemy.add(0x110).readPointer().readByteArray(24))),
   extension:extension.isNull()?null:{vtable:extension.readPointer().toString(),kind:extension.add(8).readU32(),pick_range:extension.add(0x10).readU32(),symbol:extension.add(0x14).readU32(),symbol_scale:extension.add(0x18).readFloat()},
   hp:enemy.add(0x114).readPointer().add(8).readU32()};
 }
 Interceptor.attach(address(0x51c1e0),{onEnter(args){this.keep=args[1].toUInt32()===0x72000001;},
  onLeave(ret){if(this.keep){enemy=ptr(ret.toString());emit(safely(()=>({event:'native_local_enemy_created',actor:ret.toString(),...enemyState()})));}}});
 setInterval(()=>{const s=safely(enemyState);if(!s)return;const key=JSON.stringify(s);if(key!==previous){previous=key;emit({event:'native_local_enemy_state',...s});}},500);
 for(const [va,event] of [[0x501470,'native_enemy_model_load'],[0x4fe5c0,'native_enemy_action']]){
  Interceptor.attach(address(va),{onEnter(args){this.keep=safely(()=>this.context.ecx.add(0x68).readU32())===0x72000001;this.actor=this.context.ecx;this.args=[args[0].toString(),args[1].toString()];},
   onLeave(ret){if(this.keep){enemy=this.actor;}if(this.keep && ++samples<=32)emit({event,result:ret.toInt32()&255,args:this.args,state:safely(enemyState)});}});
 }
 for(const [va,event] of [[0x49d2f0,'native_battle_group_created'],[0x529840,'native_battle_actor_created'],[0x430e50,'native_battle_init'],[0x431920,'native_battle_init_tick'],[0x5231b0,'native_battle_request_9f'],[0x522fd0,'native_battle_request_a8']]){
  Interceptor.attach(address(va),{onEnter(args){this.keep=++battleSamples<=150;this.args=[args[0].toString(),args[1].toString(),args[2].toString()];if(this.keep)emit({event,object:this.context.ecx.toString(),args:this.args});},
   onLeave(ret){if(this.keep)emit({event:event+'_returned',result:ret.toString()});}});
 }

 for(const [va,event] of [[0x4d9b90,'native_whole_model_bank_lookup'],[0x518ed0,'native_actor_model_resource_init']]){
  let n=0;
  Interceptor.attach(address(va),{onEnter(args){
   this.keep=++n<=80;this.args=Array.from({length:9},(_,i)=>args[i].toUInt32());this.object=this.context.ecx.toString();
   if(this.keep)emit({event,object:this.object,args:this.args});
  },onLeave(ret){if(this.keep)emit({event:event+'_returned',object:this.object,result:ret.toUInt32(),args:this.args});}});
 }
 for(const [va,event] of [[0x5109a0,'native_battle_actor_model_load'],[0x50fcf0,'native_battle_actor_collision_load']]){
  let n=0;
  Interceptor.attach(address(va),{onEnter(args){this.actor=this.context.ecx;this.keep=++n<=16;},
   onLeave(ret){if(this.keep)emit(safely(()=>({event,result:ret.toInt32()&255,identity:[this.actor.add(0x58).readU32(),this.actor.add(0x5c).readU32()],model:this.actor.add(0xc0).readPointer().toString(),collision_model:this.actor.add(0xc4).readPointer().toString(),resource_bank:this.actor.add(0x16c).readU32()})));}});
 }

 let symbolSamples=0;
 Interceptor.attach(address(0x501080),{onEnter(args){
  this.keep=safely(()=>this.context.ecx.add(0x68).readU32())===0x72000001;
  this.resource=args[1].toUInt32();this.actor=this.context.ecx;
 },onLeave(ret){if(this.keep && ++symbolSamples<=32)emit({event:'native_enemy_symbol_created',resource:this.resource,result:ret.toString()});}});

 let completedSamples=0;
 Interceptor.attach(address(0x522260),{onEnter(args){if(++completedSamples<=32)emit({event:'native_battle_pending_request_completed',request_id:args[0].toUInt32()});}});
 emit({event:'combat_probe_ready',mode:'Read-only original enemy and encounter observations'});
})();

// v20 read-only actor/animation snapshots, exact original callers and returns.
(function(){
 const at=va=>Process.mainModule.base.add(va-0x400000),actors=new Map(),models=new Map();
 function safe(f){try{return f();}catch(e){return {error:String(e)};}}
 function snapshot(p){
  const m=p.add(0xc0).readPointer();
  return {identity:[p.add(0x58).readU32(),p.add(0x5c).readU32()],position:[p.readFloat(),p.add(4).readFloat()],
   entity_kind:p.add(0x60).readU32(),category:p.add(0x6c).readU32(),controlled:p.add(0x68).readU8(),
   readiness:p.add(0x84).readU32(),action:p.add(0x88).readU32(),direction:p.add(0x8c).readU32(),
   dimensions:[p.add(0x140).readU32(),p.add(0x144).readU32()],flags:[p.add(0x148).readU8(),p.add(0x150).readU8(),p.add(0x168).readU8()],
   model:m.toString(),model_state:m.isNull()?null:{bank:m.readU32(),resource:m.add(4).readPointer().toString(),animation:m.add(0x38).readU32(),direction:m.add(0x3c).readU32(),fallback:m.add(0x44).readU32(),drawable:m.add(0x88).readU8(),animation_clock:m.add(0x74).readU32(),color:m.add(0x9c).readU32(),layers:m.add(0x20).readU32()}};
 }
 Interceptor.attach(at(0x529840),{onLeave(ret){
  if(ret.isNull())return;const p=ptr(ret.toString());actors.set(p.toString(),p);
  send(safe(()=>({event:'native_battle_render_actor_snapshot',phase:'created',...snapshot(p)})));
 }});
 let n=0;
 setInterval(()=>{if(actors.size && ++n<=120)for(const p of actors.values())send(safe(()=>({event:'native_battle_render_actor_snapshot',phase:'tick',sample:n,...snapshot(p)})));},1000);
 for(const [va,event] of [[0x518fc0,'native_model_animation_select'],[0x518280,'native_model_layer_select']]){
  let count=0;Interceptor.attach(at(va),{onEnter(args){
   this.p=ptr(this.context.ecx.toString());this.args=[args[0].toUInt32(),args[1].toUInt32(),args[2].toUInt32(),args[3].toUInt32()];this.keep=++count<=48;this.caller=this.returnAddress.toString();
  },onLeave(ret){if(this.keep)send({event,object:this.p.toString(),args:this.args,result:ret.toUInt32()&255,caller:this.caller});}});
 }
 for(const [va,event] of [[0x433dd0,'native_battle_main_tick'],[0x433b40,'native_battle_main_draw'],[0x432200,'native_battle_render_job']]){
  let count=0;Interceptor.attach(at(va),{onEnter(args){const n=++count;if([1,60,300,1800].includes(n))send({event,sample:n,object:this.context.ecx.toString(),args:[args[0].toString(),args[1].toString()]});}});
 }
 let draws=0;Interceptor.attach(at(0x516750),{onEnter(args){this.model=ptr(this.context.ecx.toString());this.keep=++draws<=16;this.actor=ptr(args[2].toString());},onLeave(ret){if(this.keep)send(safe(()=>({event:'native_battle_body_submitted',model:this.model.toString(),result:ret.toUInt32()&255,drawable:this.model.add(0x88).readU8(),identity:[this.actor.add(0x58).readU32(),this.actor.add(0x5c).readU32()]})));}});
 send({event:'battle_render_probe_ready',mode:'Read-only original actor and animation observation'});
})();

 // v21 read-only battle pool, target and real GUI input probes.
(function(){
 const at=va=>Process.mainModule.base.add(va-0x400000);
 const safe=f=>{try{return f();}catch(e){return {error:String(e)};}};
 const snap=p=>({identity:[p.add(0x58).readU32(),p.add(0x5c).readU32()],target:[p.add(0x98).readU32(),p.add(0x9c).readU32()],position:[p.readFloat(),p.add(4).readFloat()],controlled:p.add(0x68).readU8(),collision_model:p.add(0xc4).readPointer().toString()});
 Interceptor.attach(at(0x5146a0),{onEnter(){this.pool=this.context.ecx;},onLeave(){send(safe(()=>({event:'native_battle_pool_started',active:this.pool.add(0x14).readU32()})));}});
 Interceptor.attach(at(0x50f500),{onEnter(args){this.p=this.context.ecx;this.target=[args[0].toUInt32(),args[1].toUInt32()];},onLeave(){send(safe(()=>({event:'native_battle_target_set',requested_target:this.target,...snap(this.p)})));}});
 let inputs=0;Interceptor.attach(at(0x512ff0),{onEnter(args){if(++inputs<=12)send(safe(()=>({event:'native_battle_input_tick',sample:inputs,...snap(args[0])})));}});
 let picks=0,lastPick='';Interceptor.attach(at(0x515900),{onEnter(args){this.out=args[0];this.point=safe(()=>[args[1].readFloat(),args[1].add(4).readFloat()]);},onLeave(ret){const result=ret.toUInt32()&255,key=JSON.stringify([result,this.point]);if(++picks<=12||(key!==lastPick&&picks<30000)){lastPick=key;send(safe(()=>({event:'native_battle_mouse_pick',result,point:this.point,count:this.out.add(8).readU32()})));}}});
 Interceptor.attach(at(0x522fd0),{onEnter(args){send({event:'native_battle_attack_command',command:args[0].toUInt32()});}});
 send({event:'battle_input_probe_ready',mode:'Read-only native battle target, pool and attack observations'});
})();

(function(){
 const at=va=>Process.mainModule.base.add(va-0x400000);
 function safe(f){try{return f();}catch(e){return {error:String(e)};}}
 let count=0;
 Interceptor.attach(at(0x510090),{onEnter(args){
  this.keep=++count<=64;this.actor=this.context.ecx;this.fromInput=args[1].toUInt32()&255;
  this.action=safe(()=>({position:[args[0].readFloat(),args[0].add(4).readFloat()],direction:args[0].add(8).readU32(),command:args[0].add(12).readU32(),target:[args[0].add(24).readU32(),args[0].add(28).readU32()]}));
 },onLeave(ret){if(this.keep)send(safe(()=>({event:'native_battle_actor_action_applied',from_input:this.fromInput,action:this.action,result:ret.toUInt32()&255,identity:[this.actor.add(0x58).readU32(),this.actor.add(0x5c).readU32()]})));}});
 send({event:'battle_action_probe_ready',mode:'Read-only original action record application'});
})();
