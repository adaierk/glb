'use strict';
// Additional read-only observations; bootstrap_runtime.js supplies loopback routing.
(function () {
  const emit = x => send(x);
  const address = va => Process.mainModule.base.add(va - 0x400000);
  function safely(f) { try { return f(); } catch (e) { return {error:String(e)}; } }
  function bytes(p,n) {
    return Array.from(new Uint8Array(p.readByteArray(Math.min(n,4096))))
      .map(x=>x.toString(16).padStart(2,'0')).join('');
  }
  function header(p,n) {
    return safely(()=>({flags:p.readU8(),opcode:p.add(1).readU16(),
      bytes:n,declared_bytes:p.add(3).readU16(),request_id:p.add(5).readU32(),
      hex:bytes(p,n)}));
  }
  function wrapper(p) {
    return safely(()=>({wrapper:p.toString(),vtable:p.readPointer().toString(),
      receive_handler:p.readPointer().add(0x14).readPointer().toString(),
      cipher_object:p.add(0x14).readPointer().toString(),
      send_compressor:p.add(0x44).readPointer().toString(),
      compression_option:p.add(0x48).readU32(),
      receive_decompressor:p.add(0x4c).readPointer().toString(),
      transport_mode:address(0x80b758).readU8()}));
  }
  let sent=0,received=0;
  Interceptor.attach(address(0x61f920), {
    onEnter(args) {
      this.p=args[3];this.keep=++sent<=250;
      if(this.keep)emit({event:'native_plain_request_before_serialization',
        ...wrapper(this.context.ecx),...header(this.p,this.p.add(3).readU16())});
    },
    onLeave(ret) {
      if(this.keep)emit({event:'native_request_serialized',result_bytes:ret.toInt32(),
        ...header(this.p,this.p.add(3).readU16())});
    }
  });
  Interceptor.attach(address(0x6095d0), {
    onEnter(args) {
      if(++received<=250)emit({event:'native_response_correlated',module:this.context.ecx.toString(),
        request_id:args[0].toUInt32(),ack_only:args[1].isNull(),
        ...(args[1].isNull()?{}:header(args[1],args[2].toInt32()))});
    }
  });
  Interceptor.attach(address(0x61d9e0), {
    onEnter() { this.p=this.context.ecx;this.before=this.p.add(0x18).readS32(); },
    onLeave() {
      const after=this.p.add(0x18).readS32();
      if(after!==this.before)emit({event:'native_account_state_changed',before:this.before,after});
      if(this.before===2 && after===1) {
        const result=this.p.add(0x20).readPointer();
        if(!result.isNull()) {
          const sid=result.add(0x4c).readU32();
          if(sid!==0)emit({event:'ACCOUNT_AUTHENTICATED_NATIVE',
            account_id:result.add(0x48).readU32(),login_sid:sid});
        }
      }
    }
  });
  Interceptor.attach(address(0x4493d2), {
    onEnter() { emit({event:'GAME_PRELOGIN_ACCEPTED_NATIVE',
      note:'Original identity/UID checks and UI continuation reached'}); }
  });
  Interceptor.attach(address(0x43894d), {
    onEnter() {
      const fields=this.context.edi.add(0x14).readPointer();
      const begin=fields.add(0x48).readPointer(),end=fields.add(0x4c).readPointer();
      emit({event:'CHARACTER_LIST_ACCEPTED_NATIVE',
        count:end.sub(begin).toUInt32()/0x118,available_slots:fields.add(0x58).readU32()});
    }
  });
  for(const [va,event] of [[0x438ce2,'CHARACTER_CREATED_NATIVE']]) {
    try {Interceptor.attach(address(va), {onEnter() {emit({event});}});}
    catch(e) {emit({event:'optional_native_hook_unavailable',native_event:event,error:String(e)});}
  }
  Interceptor.attach(address(0x5308e0), {
    onEnter(args) {
      emit(safely(()=>({event:'WORLD_ROUTE_CONVERSION_ENTERED_NATIVE',count:args[1].toUInt32(),
        identity:[args[2].toUInt32(),args[3].toUInt32()],
        link_hex:bytes(args[0],Math.min(args[1].toUInt32(),5)*12)})));
    }
  });
  Interceptor.attach(address(0x43d2c0), {
    onEnter(args) {
      const p=args[1];
      if(p.add(1).readU16()===4 && p.add(3).readU16()===13)
        emit({event:'WORLD_ACCOUNT_ID_REQUEST_OBSERVED_NATIVE',account_id:p.add(9).readU32(),
          note:'Request observed before broadcast send; no acceptance or map success inferred'});
    }
  });
  Interceptor.attach(address(0x620760), {
    onEnter() {this.controller=this.context.ecx;this.stage=this.controller.add(0x2c).readU32();},
    onLeave() {
      const after=this.controller.add(0x2c).readU32();
      if(this.stage===6 && after===7)emit({event:'WORLD_ADMISSION_ACK_ACCEPTED_NATIVE',
        before:6,after:7,note:'Original world admission wait completed; map state is not inferred'});
      if(this.stage===8 && after===9 && this.controller.add(0x30).readU32()===2)
        emit({event:'WORLD_CONTROLLER_COMPLETED_NATIVE',before:8,after:9,result:2,
          note:'Original account-control wait completed; socket startup and map must be verified separately'});
    }
  });
  for(const va of [0x530600,0x52a580]) {
    Interceptor.attach(address(va), {
      onEnter(args) {
        this.keep=received<250;this.op=args[1].add(1).readU16();
        if(this.keep)emit({event:'native_game_incoming',handler:'0x'+va.toString(16),
          ...header(args[1],args[2].toInt32())});
      },
      onLeave(ret){if(this.keep)emit({event:'native_game_incoming_returned',handler:'0x'+va.toString(16),opcode:this.op,result:ret.toInt32()});}
    });
  }
  let nameCalls=0;
  Interceptor.attach(address(0x430b50),{onEnter(args){this.keep=++nameCalls<=20;this.dest=args[0];
    this.caller=this.returnAddress.toString();
  },onLeave(ret){if(this.keep)emit(safely(()=>({event:'native_world_name_decode',caller:this.caller,
    result:ret.toInt32(),name:this.dest.readUtf16String()})));}});
  Interceptor.attach(address(0x6897f0), {
    onEnter(args) {
      const id=args[0].toUInt32();
      if(id>=7 && id<=10 || id===17) {
        emit({event:'native_task_transition_requested',id,manager:this.context.ecx.toString(),
          manager_hex:bytes(this.context.ecx,64),factory:args[1].toString(),cleanup:args[2].toString()});
        if(id===7 && args[1].equals(address(0x440180)))emit({event:'CHARACTER_SELECTION_ACCEPTED_NATIVE'});
      }
    }
  });
  for(const [va,event] of [[0x440180,'native_world_task_construct'],[0x43ef50,'native_map_init_request'],
                          [0x43f090,'native_map_init_parse'],[0x442270,'native_map_load_construct']]) {
    Interceptor.attach(address(va),{onEnter(args){this.args=args;emit({event,object:this.context.ecx.toString()});},onLeave(ret){emit({event:event+'_returned',result:ret.toInt32()});}});
  }
  Interceptor.attach(address(0x4c8570),{onEnter(args){emit({event:'native_game_error',code:args[0].toInt32()});}});
  const observedMapTasks=new Set();
  for(const [va,name] of [[0x4414f0,'map_ready_request'],[0x4416e0,'map_ready_wait'],
                         [0x52a200,'map_ready_reply_apply'],[0x441870,'map_enter_transition']]) {
    Interceptor.attach(address(va),{onEnter(){const object=this.context.ecx.toString(),key=name+object;
      if(!observedMapTasks.has(key)){observedMapTasks.add(key);emit({event:'native_'+name,object});}}});
  }
  for(const [va,name] of [[0x4c1bb0,'map_engine_create'],[0x4c1330,'map_engine_init'],
                         [0x4543d0,'map_resource_load'],[0x420120,'map_mpi_read'],
                         [0x4181f0,'map_mpd_read'],[0x45c880,'map_bank_read'],
                         [0x509db0,'player_entity_create'],[0x501470,'player_model_load']]) {
    Interceptor.attach(address(va),{
      onEnter(args){this.object=this.context.ecx;this.name=name;
        const paths=va===0x4543d0?[args[1],args[2],args[3]]:
          (va===0x420120 || va===0x4181f0)?[args[0]]:va===0x45c880?[args[1]]:[];
        this.keep=va!==0x45c880 || paths.some(p=>safely(()=>p.readCString().includes('1110101'))===true);
        if(this.keep)emit({event:'native_'+name,object:this.object.toString(),
          paths:paths.map(p=>safely(()=>p.readCString()))});},
      onLeave(ret){if(this.keep)emit({event:'native_'+name+'_returned',object:this.object.toString(),
        result:ret.toInt32(),result_low_byte:ret.toInt32()&255});}
    });
  }
  let lastRenderState='',renderSamples=0;
  Interceptor.attach(address(0x4455f0),{onEnter(args){
    if(++renderSamples%120!==1)return;
    const state=safely(()=>{
      const g=address(0x80dbf4).readPointer().add(0x28).readPointer().add(0x28).readPointer().add(0x2c).readPointer();
      const selected=g.add(0x28).readPointer(),world=g.add(0x74).readPointer();
      const player=g.add(0x78).readPointer().add(0xc).readPointer();
      return {event:'native_world_render_state',task:bytes(args[0],24),
        current_map_id:selected.add(0x20).readU32(),
        world_gate:world.add(0x258).readU32(),world_flags:bytes(world.add(0x1c4),48),
        player:player.toString(),position:[player.add(0xc).readFloat(),player.add(0x10).readFloat()],
        player_instance:player.add(0x14).readU32(),player_controlled:player.add(0x80).readU8(),
        movement_permitted:player.add(0x144).readU8(),
        path_state:safely(()=>{const p=player.add(0x12c).readPointer();return {object:p.toString(),
          index:p.add(0x14).readS32(),point:[p.add(4).readFloat(),p.add(8).readFloat()],
          target:[p.add(0x54).readFloat(),p.add(0x58).readFloat()],hex:bytes(p,0x68)};}),
        world_viewport:[world.readS32(),world.add(4).readS32(),world.add(8).readS32(),world.add(12).readS32()],
        world_mouse:[world.add(0x2c).readFloat(),world.add(0x30).readFloat()],
        world_input_flags:bytes(world.add(0x78),0x70),profile:bytes(player.add(0x114).readPointer(),48)};
    });
    const key=JSON.stringify(state);if(key!==lastRenderState){lastRenderState=key;emit(state);}
  }});
  let drew=false;
  const lastInputGates=new Map();let inputGateChanges=0;
  for(const va of [0x524670,0x4bb190,0x500ab0,0x500020,0x4ca9b0,0x4feca0]){
    Interceptor.attach(address(va),{onEnter(){
      this.keep=drew && this.returnAddress.compare(address(0x505200))>=0 && this.returnAddress.compare(address(0x505f40))<0;
      this.caller=this.returnAddress.toString();
    },onLeave(ret){
      if(!this.keep)return;
      const key=va+this.caller,value=ret.toInt32()&255;
      if(lastInputGates.get(key)!==value && ++inputGateChanges<=80){
        lastInputGates.set(key,value);emit({event:'native_player_input_gate',function:'0x'+va.toString(16),caller:this.caller,result:value});
      }
    }});
  }
  let pickCalls=0;
  Interceptor.attach(address(0x50a3e0),{onEnter(args){
    this.keep=drew && (this.returnAddress.equals(address(0x5059d4)) || this.returnAddress.equals(address(0x50585e))) && ++pickCalls<=40;
    this.list=args[0];this.caller=this.returnAddress.toString();
    if(this.keep)emit(safely(()=>({event:'native_player_pick_enter',caller:this.caller,
      point:[args[1].readFloat(),args[1].add(4).readFloat()],options:[args[4].toInt32(),args[5].toInt32(),args[6].toInt32()]})));
  },onLeave(ret){if(this.keep)emit(safely(()=>({event:'native_player_pick_result',caller:this.caller,result:ret.toInt32()&255,count:this.list.add(8).readU32()})));}});
  const lastBindings=new Map();let bindingChanges=0;
  Interceptor.attach(address(0x69b790),{onEnter(args){
    this.keep=drew && this.returnAddress.compare(address(0x505200))>=0 && this.returnAddress.compare(address(0x505f40))<0;
    this.id=args[0].toInt32();this.caller=this.returnAddress.toString();
  },onLeave(ret){
    if(!this.keep || ret.isNull())return;
    const value=safely(()=>ret.readU16()),key=this.id;
    if(lastBindings.get(key)!==value && ++bindingChanges<=150){
      lastBindings.set(key,value);emit({event:'native_player_binding_state',id:key,state:value,caller:this.caller});
    }
  }});
  let buttonChanges=0;const lastButtons=new Map();
  Interceptor.attach(address(0x68e290),{onEnter(args){
    this.keep=drew && this.returnAddress.compare(address(0x505200))>=0 && this.returnAddress.compare(address(0x505f40))<0;
    this.id=args[0].toInt32();this.caller=this.returnAddress.toString();
  },onLeave(ret){
    if(!this.keep)return;
    const value=ret.toInt32()&255,key=this.id;
    if(lastButtons.get(key)!==value && ++buttonChanges<=100){
      lastButtons.set(key,value);emit({event:'native_player_mouse_button',id:key,state:value,caller:this.caller});
    }
  }});
  let inputTicks=0;
  Interceptor.attach(address(0x505200),{onEnter(args){
    if(++inputTicks%120!==1)return;
    emit(safely(()=>({event:'native_player_input_tick',
      actor:args[0].toString(),controlled:args[0].add(0x80).readU8(),
      actor_flags:bytes(args[0].add(0x70),40),actor_modes:bytes(args[0].add(0x134),32)})));
  }});
  let moveCalls=0,lastMoveKey='';
  for(const va of [0x4205b0,0x422d70]){
    let calls=0;
    Interceptor.attach(address(va),{onEnter(args){
      this.keep=++calls<=60;this.p=this.context.ecx;
      if(this.keep)emit(safely(()=>({event:'native_path_internal_enter',function:'0x'+va.toString(16),caller:this.returnAddress.toString(),
        object:this.p.toString(),map_binding:this.p.add(0x34).readPointer().toString(),
        args:[args[0].toString(),args[1].toString(),args[2].toString()],hex:bytes(this.p,0x64)})));
    },onLeave(ret){if(this.keep)emit(safely(()=>({event:'native_path_internal_result',function:'0x'+va.toString(16),
      result:ret.toInt32(),map_binding:this.p.add(0x34).readPointer().toString()})));}});
  }
  Interceptor.attach(address(0x415090),{onEnter(args){this.map=this.context.ecx;
    emit({event:'native_map_navigation_apply',object:this.map.toString(),value:args[2].toUInt32()});
  },onLeave(){emit(safely(()=>{const p=this.map,base=p.add(4).readPointer(),stride=p.add(0xa4).readS32();
    const cells=[[6,4],[10,8],[19,7],[13,21]].map(g=>({grid:g,flags:base.add((g[1]*stride+Math.trunc(g[0]/2))*12).readU32()}));
    return {event:'native_map_navigation_applied',width:p.add(0xd8).readS32(),height:p.add(0xdc).readS32(),
      resource_dimensions:[stride,p.add(0xa8).readS32()],primary_cells:p.add(8).readPointer().sub(base).toInt32()/12,cells};
  }));}});
  Interceptor.attach(address(0x4fe6c0),{onEnter(args){
    emit({event:'native_actor_movement_permission',actor:this.context.ecx.toString(),enabled:args[0].toInt32()&255,
      caller:this.returnAddress.toString()});
  }});
  Interceptor.attach(address(0x502250),{onEnter(args){
    const key=safely(()=>args[0].readS32()+','+args[0].add(4).readS32()+','+args[1]+','+args[2]+','+args[3]);
    this.keep=++moveCalls<=4 || key!==lastMoveKey;lastMoveKey=key;
    if(this.keep)emit(safely(()=>({event:'native_move_path_request',
      player:this.context.ecx.toString(),target_grid:[args[0].readS32(),args[0].add(4).readS32()],
      options:[args[1].toInt32(),args[2].toInt32(),args[3].toInt32()],
      position:[this.context.ecx.add(0xc).readFloat(),this.context.ecx.add(0x10).readFloat()],
      planner:safely(()=>{const p=this.context.ecx.add(0x124).readPointer();return {object:p.toString(),hex:bytes(p,0x64),map:p.add(0x34).readPointer().toString()};})}))); 
  },onLeave(ret){if(this.keep)emit({event:'native_move_path_result',result:ret.toInt32()});}});
  Interceptor.attach(address(0x454090),{onEnter(){
    if(!drew){drew=true;emit({event:'native_map_draw_context',object:this.context.ecx.toString()});}
  }});
  let worldTaskPhase=-1;
  Interceptor.attach(address(0x43eb50), {
    onEnter() {
      const phase=safely(()=>this.context.ecx.add(0x14).readPointer().add(4).readU32());
      if(phase!==worldTaskPhase) {worldTaskPhase=phase;emit({event:'native_world_task_phase',phase});}
    }
  });
  for(const [va,name] of [[0x61e9f0,'world_relogin'],[0x61ec50,'world_endpoint_answer']]) {
    Interceptor.attach(address(va),{
      onEnter(args) {this.p=this.context.ecx;emit({event:'native_'+name+'_enter',controller:this.p.toString(),
        args:[args[0].toString(),args[1].toString()],stage:this.p.add(0x2c).readU32()});},
      onLeave(ret) {emit({event:'native_'+name+'_leave',result:ret.toInt32(),
        stage:this.p.add(0x2c).readU32(),status:this.p.add(0x34).readS32()});}
    });
  }
  Interceptor.attach(address(0x51c1e0),{onEnter(args){
    this.keep=args[1].toUInt32()===0x70000001;
    if(this.keep)emit({event:'native_local_shop_create_enter',map:args[0].toUInt32(),identity:[args[1].toUInt32(),args[2].toUInt32()]});
  },onLeave(ret){if(this.keep)emit(safely(()=>({event:'native_local_shop_create_result',actor:ret.toString(),
    category:ret.isNull()?null:ret.add(0x70).readU32(),
    position:ret.isNull()?null:[ret.add(0xc).readFloat(),ret.add(0x10).readFloat()],
    extension:ret.isNull()?null:ret.add(0x84).readPointer().toString()})));}});
  Interceptor.attach(address(0x4fe510),{onEnter(args){
    if(args[0].isNull())return;
    if(safely(()=>args[0].readPointer().equals(address(0x6eeca8))))
      emit({event:'native_shop_extension_attached',actor:this.context.ecx.toString(),extension:args[0].toString()});
  }});
  emit({event:'runtime_account_probe_ready',
    note:'Observes original account/character mutation and route paths; never writes game state'});
})();
