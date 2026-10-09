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
        this.keep=va!==0x45c880 || paths.some(p=>safely(()=>/1110101|1120108/.test(p.readCString()))===true);
        if(this.keep)emit({event:'native_'+name,object:this.object.toString(),
          paths:paths.map(p=>safely(()=>p.readCString()))});},
      onLeave(ret){if(this.keep)emit({event:'native_'+name+'_returned',object:this.object.toString(),
        result:ret.toInt32(),result_low_byte:ret.toInt32()&255});}
    });
  }
  let lastRenderState='',renderSamples=0;
  let observedPlayer=null;
  Interceptor.attach(address(0x4455f0),{onEnter(args){
    if(++renderSamples%120!==1)return;
    const state=safely(()=>{
      const g=address(0x80dbf4).readPointer().add(0x28).readPointer().add(0x28).readPointer().add(0x2c).readPointer();
      const selected=g.add(0x28).readPointer(),world=g.add(0x74).readPointer();
      const player=g.add(0x78).readPointer().add(0xc).readPointer();
      observedPlayer=player;
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
        world_camera_fields:bytes(world.add(0x10),28),
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
  },onLeave(ret){if(this.keep)emit(safely(()=>{
    const count=this.list.add(8).readU32(),actors=[];
    const head=this.list.add(4).readPointer();let node=head.readPointer();
    for(let i=0;i<Math.min(count,8) && !node.equals(head);i++,node=node.readPointer()){
      const actor=node.add(8).readPointer();
      actors.push({identity:[actor.add(0x68).readU32(),actor.add(0x6c).readU32()],category:actor.add(0x70).readU32()});
    }
    return {event:'native_player_pick_result',caller:this.caller,result:ret.toInt32()&255,count,actors};
  }));}});
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
    if(!drew){drew=true;emit(safely(()=>({event:'native_map_draw_context',object:this.context.ecx.toString(),
      screen_translation:[this.context.esp.add(8).readFloat(),this.context.esp.add(12).readFloat()],
      args:bytes(this.context.esp.add(4),32)})));}
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
    extension:ret.isNull()?null:ret.add(0x64).readPointer().toString()})));}});
  Interceptor.attach(address(0x4fe510),{onEnter(args){
    if(args[0].isNull())return;
    if(safely(()=>args[0].readPointer().equals(address(0x6eeca8))))
      emit({event:'native_shop_extension_attached',actor:this.context.ecx.toString(),extension:args[0].toString()});
  }});
  Interceptor.attach(address(0x5b9a90),{onEnter(args){
    emit({event:'native_npc_actions',identity:[args[0].toUInt32(),args[1].toUInt32()],permissions:args[2].toUInt32(),extra:args[3].toUInt32()});
  }});
  Interceptor.attach(address(0x4feb70),{onEnter(args){
    emit(safely(()=>({event:'native_actor_target_set',actor:[this.context.ecx.add(0x68).readU32(),this.context.ecx.add(0x6c).readU32()],
      target:[args[0].toUInt32(),args[1].toUInt32()]})));
  }});
  let observedShopFrame=null;
  let observedInventoryFrame=null;
  Interceptor.attach(address(0x5b52d0),{onLeave(ret){if(!ret.isNull())observedInventoryFrame=ret;}});
  setInterval(()=>{if(observedInventoryFrame!==null)emit(safely(()=>({event:'native_inventory_frame_state',
    visible:!!(observedInventoryFrame.add(0x20).readU32()&32),frame:observedInventoryFrame.toString()})));},500);
  Interceptor.attach(address(0x51ea20),{onEnter(args){
    if(observedShopFrame!==null && this.context.ecx.equals(observedShopFrame.add(0x114))) {
      const item=args[1];
      emit(safely(()=>({event:'native_shop_item_insert',item:item.toString(),
        price_gald:item.add(0x11c).readU32(),template_pointer:item.add(0x30).readPointer().toString(),
        catalog_display_value:item.add(0xa4).readU32(),local_catalog_row:item.add(0x10).readU32()})));
    }
  }});
  Interceptor.attach(address(0x5998f0),{onEnter(args){
    if(observedShopFrame!==null && (this.context.ecx.equals(observedShopFrame.add(0x680)) ||
        this.context.ecx.equals(observedShopFrame.add(0x1c0c))))
      emit(safely(()=>({event:'native_shop_row_render',row:args[0].toInt32(),name:args[4].readUtf16String(),
        template_pointer:args[2].toString(),catalog_display_value:args[6].toUInt32(),
        quantity:args[5].toInt32(),mode:observedShopFrame.add(0x110).readU32()})));
  }});
  let activePriceWidget=null,priceAssignments=0;const observedPriceTexts=new Set();
  Interceptor.attach(address(0x596eb0),{onEnter(args){
    if(observedShopFrame!==null && !args[0].isNull() && priceAssignments<60){
      this.previous=activePriceWidget;activePriceWidget=this.context.ecx.add(0x44c);this.keep=true;
    }
  },onLeave(){if(this.keep)activePriceWidget=this.previous;}});
  Interceptor.attach(address(0x5c12f0),{onEnter(args){
    if(activePriceWidget!==null && this.context.ecx.equals(activePriceWidget)){
      const value=safely(()=>args[0].readUtf16String());
      if(!observedPriceTexts.has(value) && ++priceAssignments<=60){
        observedPriceTexts.add(value);emit({event:'native_shop_display_price_text',text:value});
      }
    }
  }});
  Interceptor.attach(address(0x59a640),{onEnter(args){
    this.shop=this.context.ecx;this.size=args[1].toUInt32();
    observedShopFrame=this.shop;
    emit(safely(()=>({event:'native_shop_catalog_parse_enter',bytes:this.size,opcode:args[0].add(1).readU16()})));
  },onLeave(ret){emit(safely(()=>({event:'native_shop_catalog_parse_result',result:ret.toInt32()&255,
    target:[this.shop.add(0x100).readU32(),this.shop.add(0x104).readU32()],items:this.shop.add(0x11c).readU32()})));}});
  Interceptor.attach(address(0x59a5d0),{onEnter(args){this.argument=args[0].toInt32();},
    onLeave(ret){emit({event:'native_shop_frame_show',argument:this.argument,result:ret.toInt32()&255});}});
  Interceptor.attach(address(0x599bd0),{onEnter(){this.shop=this.context.ecx;
    this.keep=safely(()=>this.shop.add(0x100).readU32()===0x70000001 && this.shop.add(0x104).readU32()===1);
  },onLeave(ret){if(this.keep)emit(safely(()=>({event:'native_shop_frame_closed',result:ret.toInt32()&255,
    target:[this.shop.add(0x100).readU32(),this.shop.add(0x104).readU32()]})));}});
  Interceptor.attach(address(0x5c1a10),{onEnter(args){
    this.frame=this.context.ecx;
    this.keep=observedShopFrame!==null && this.frame.equals(observedShopFrame);
    if(this.keep){this.argument=args[0].toInt32();this.before=this.frame.add(0x20).readU32();}
  },onLeave(){if(this.keep)emit(safely(()=>({event:'native_shop_visibility_change',argument:this.argument,
    flags_before:this.before,flags_after:this.frame.add(0x20).readU32(),
    visible:(this.frame.add(0x20).readU32()&0x20)!==0})));}});
  // Original 5C1A90 queries visibility from frame+20 bit 5. Read only;
  // the title-bar close hides this frame without the server D8 cleanup path.
  setInterval(()=>{if(observedShopFrame!==null)emit(safely(()=>({event:'native_shop_frame_state',
    frame:observedShopFrame.toString(),visible:(observedShopFrame.add(0x20).readU32()&0x20)!==0,
    target:[observedShopFrame.add(0x100).readU32(),observedShopFrame.add(0x104).readU32()]})));},1000);
  // v14: transaction/inventory observations only. No NativeFunction calls,
  // state writes, UI bypass or replacement game rendering.
  let shopInputSamples=0;
  Interceptor.attach(address(0x59ad30),{onEnter(args){
    if(observedShopFrame!==null && ++shopInputSamples<=120)emit({event:'native_shop_input',
      object:this.context.ecx.toString(),kind:args[0].toUInt32(),arguments:[1,2,3,4].map(x=>args[x].toString())});
  }});
  Interceptor.attach(address(0x59a950),{onEnter(args){emit({event:'native_shop_choose_catalog',row:args[0].toInt32()});}});
  Interceptor.attach(address(0x597090),{onEnter(){this.keep=observedShopFrame!==null;},
    onLeave(ret){if(this.keep)emit({event:'native_shop_hit_test',row:ret.toInt32()});}});
  Interceptor.attach(address(0x596690),{onEnter(args){this.item=args[0];this.quantity=args[1].toInt32();this.output=args[2];},
    onLeave(ret){emit(safely(()=>({event:'native_shop_quantity_check',requested:this.quantity,result:ret.toInt32()&255,
      accepted:this.output.readS32(),flags:this.item.add(0x14).readU32(),max_stack:this.item.add(0x26).readS16(),
      buy_price:this.item.add(0xa4).readU32(),sell_price:this.item.add(0xa8).readU32()})));}});
  let observedCart=null;
  Interceptor.attach(address(0x59a2a0),{onEnter(){this.cart=this.context.ecx;observedCart=this.cart;},onLeave(ret){
    emit(safely(()=>({event:'native_shop_cart_add_result',result:ret.toInt32()&255,
      lines:this.cart.add(0xef4).readU32(),total:this.cart.add(0xefc).readU32(),mode:this.cart.add(0xee8).readU32()})));}});
  setInterval(()=>{if(observedCart!==null)emit(safely(()=>{
    const count=observedCart.add(0xef4).readU32(),head=observedCart.add(0xef0).readPointer();
    const item=count && !head.isNull()?head.readPointer().add(8).readPointer():null;
    return {event:'native_shop_cart_state',mode:observedCart.add(0xee8).readU32(),lines:count,
      total:observedCart.add(0xefc).readU32(),quantity:item===null?0:item.add(0x24).readS16()};
  }));},500);
  Interceptor.attach(address(0x598950),{onEnter(){this.cart=this.context.ecx;
    emit(safely(()=>({event:'native_shop_cart_submit',mode:this.cart.add(0xee8).readU32(),
      lines:this.cart.add(0xef4).readU32(),total:this.cart.add(0xefc).readU32()})));}});
  for(const [va,kind] of [[0x4f8050,'buy'],[0x4f81b0,'sell']]){
    Interceptor.attach(address(va),{onEnter(args){this.kind=kind;this.controller=this.context.ecx;
      emit({event:'native_trade_builder_enter',kind:kind,merchant:[args[0].toUInt32(),args[1].toUInt32()],
        lines:args[2].toUInt32(),controller:this.controller.toString(),sequence_before:this.controller.readU32()});
    },onLeave(ret){emit({event:'native_trade_builder_result',kind:this.kind,result:ret.toInt32()&255,
      sequence_after:this.controller.readU32(),pending:this.controller.add(0x10).readPointer().toString()});}});
  }
  Interceptor.attach(address(0x4fab30),{onEnter(args){this.controller=this.context.ecx;
    emit(safely(()=>({event:'native_trade_reply_enter',sequence:args[0].add(12).readU32(),
      status:args[0].add(20).readS16(),pending:this.controller.add(0x10).readPointer().toString()})));
  },onLeave(){emit(safely(()=>({event:'native_trade_reply_leave',applied_sequence:this.controller.add(4).readU32(),
    pending:this.controller.add(0x10).readPointer().toString()})));}});
  Interceptor.attach(address(0x51d740),{onEnter(args){this.wallet=this.context.ecx;this.money=args[0].toInt32();},
    onLeave(){emit(safely(()=>({event:'native_wallet_set',object:this.wallet.toString(),requested:this.money,
      money:this.wallet.readU32(),checksum:this.wallet.add(4).readU32()})));}});
  Interceptor.attach(address(0x51f030),{onEnter(args){this.container=args[1];this.keep=!this.container.isNull();},
    onLeave(ret){if(this.keep)emit(safely(()=>({event:'native_inventory_records_result',result:ret.toInt32()&255,
      capacity:this.container.add(12).readU32(),items:this.container.add(8).readU32()})));}});
  Interceptor.attach(address(0x51d930),{onEnter(){this.item=this.context.ecx;},onLeave(){
    emit(safely(()=>({event:'native_inventory_named_item',identity:[0,4,8,12].map(x=>this.item.add(x).readU32()),
      name:safely(()=>{const s=this.item.add(0x34);return (s.add(24).readU32()>=8?s.add(4).readPointer():s.add(4)).readUtf16String();}),quantity:this.item.add(0x24).readS16(),
      stack_capacity:this.item.add(0x26).readS16(),sell_price:this.item.add(0xa8).readU32(),
      template_pointer:this.item.add(0x30).readPointer().toString()})));}});
  Interceptor.attach(address(0x565210),{onEnter(args){emit(safely(()=>({event:'native_inventory_ui_item',
    identity:[0,4,8,12].map(x=>args[0].add(x).readU32()),slot:args[1].toInt32(),
    template_pointer:args[2].toString(),quantity:args[3].toInt32(),flags:args[4].toUInt32()})));}});
  let previousInventory='';setInterval(()=>{if(observedPlayer!==null)emit(safely(()=>{
    const wallet=observedPlayer.add(0x1d4).readPointer(),bag=observedPlayer.add(0x1d8).readPointer();
    const state={event:'native_player_inventory_state',money:wallet.isNull()?null:wallet.readU32(),
      items:bag.isNull()?null:bag.add(8).readU32(),capacity:bag.isNull()?null:bag.add(12).readU32()};
    const key=JSON.stringify(state);if(key===previousInventory)return {event:'native_inventory_sample_unchanged'};
    previousInventory=key;return state;
  }));},1000);
  emit({event:'runtime_account_probe_ready',
    note:'Observes original account/character mutation and route paths; never writes game state'});
})();
