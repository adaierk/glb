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
  Interceptor.attach(address(0x6897f0), {
    onEnter(args) {
      const id=args[0].toUInt32();
      if(id>=7 && id<=9 || id===17) {
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
  emit({event:'runtime_account_probe_ready',
    note:'Observes original account/character mutation and route paths; never writes game state'});
})();
