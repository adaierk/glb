"""Original C6/C7 -> native action/C8, and D6 empty-catalog parsing.

GUI construction, entity collection lookups and command/transport boundaries are
declared substitutions. No packet fields or original action switches are patched.
The fixture alone does not establish real Windows NPC picking or GUI rendering.
"""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EBP,UC_X86_REG_EBX,UC_X86_REG_EDI,UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX,UC_X86_REG_EIP
from emulate_map_initialization import MapFixture
from world_npc_packets import SHOP_IDENTITY,SHOP_GRID,parse_npc_request,actor_target_reply,npc_selection_reply,shop_open_notice
from world_map_packets import LOCAL_MAP_ID

class InteractionFixture(MapFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.actors,self.player,self.npc,self.shop,self.packet=0x10d0000,0x10d1000,0x10d2000,0x10d3000,0x10d7000
        self.write32(self.game+0x78,self.actors);self.write32(self.actors+12,self.player)
        self.write32(self.game+0x44,self.ui);self.write32(self.netstate+0x48,0x10d8000)
        self.write32(self.login+4,0x10da000);self.write32(0x10da004,0x10db000) # initialized transport handles
        self.uc.mem_write(self.netstate+0x34,b'\x01')
        self.uc.mem_write(self.player+0x68,struct.pack('<II',1,1));self.write32(self.player+0x14,LOCAL_MAP_ID)
        self.write32(self.player+0x10c,self.actors)
        self.sent=[];self.disposals=0;self.shop_parse_result=None;self.opened=False

    def on_code(self,uc,va,size,x):
        sp=uc.reg_read(UC_X86_REG_ESP);obj=uc.reg_read(UC_X86_REG_ECX)
        if va in (0x526340,0x49c840,0x508a80):
            identity=struct.unpack('<II',uc.mem_read(sp+4,8))
            self.ret(self.player if identity==(1,1) else self.npc if identity==SHOP_IDENTITY else 0,
                     16 if va==0x526340 else 8) # collection lookup; identity reads remain native
        elif va==0x43d2c0:
            p=self.read32(sp+8);n=struct.unpack('<H',uc.mem_read(p+3,2))[0]
            self.sent.append(bytes(uc.mem_read(p,n)));self.ret(1,16) # native query enqueue boundary
        elif va in (0x613b40,0x43a570):
            p=self.read32(sp+12);n=struct.unpack('<H',uc.mem_read(p+3,2))[0]
            self.sent.append(bytes(uc.mem_read(p,n)));self.ret(1,12) # native-built transport capture
        elif va==0x522280:self.ret(1,12) # command response transport boundary
        elif va==0x4cacb0:self.disposals+=1;self.ret() # pending command lifetime boundary
        elif va==0x5d8fb0:uc.mem_write(obj,bytes(16));self.ret(obj) # exact-sized temporary menu object
        elif va==0x5d8fd0:self.ret(1,4) # native menu attached to initialized UI
        elif va==0x5d8fc0:self.ret() # menu GUI destruction
        elif va==0x5b5350:self.ret(self.shop) # UI shop frame getter
        elif va==0x5b9070:self.ret(1,4) # selected-target HUD refresh boundary
        elif va==0x5c12f0:self.ret(1,4) # existing shop caption resource
        elif va in (0x598540,0x599c60):self.ret() # item control clear/refresh; no catalog items yet
        elif va==0x52d579:self.shop_parse_result=uc.reg_read(UC_X86_REG_EAX)&255
        elif va==0x59a5d0:self.opened=True;self.ret(1,4) # graphic focus/show boundary
        elif va==0x52fee4:uc.emu_stop()
        else:super().on_code(uc,va,size,x)

    def receive(self,va,payload):
        self.uc.mem_write(self.packet,payload)
        self.uc.reg_write(UC_X86_REG_EBX,self.packet);self.uc.reg_write(UC_X86_REG_EDI,0)
        self.uc.reg_write(UC_X86_REG_EBP,0x20fd000);self.uc.reg_write(UC_X86_REG_ESP,0x20fc000)
        # Dispatcher supplied size for D6; original handlers consume this register.
        from unicorn.x86_const import UC_X86_REG_ESI
        self.uc.reg_write(UC_X86_REG_ESI,len(payload))
        self.uc.emu_start(va,0x52fee4,count=20000)
        if self.uc.reg_read(UC_X86_REG_EIP)!=0x52fee4:raise RuntimeError('Native handler did not finish')

def run(binary):
    f=InteractionFixture(binary);grid=0x10d9000
    target=parse_npc_request(bytes.fromhex('004e003000160000000e0292300000000100000001000000010111010000000000000000010000700100000000ffffff'))
    f.receive(0x52b5aa,actor_target_reply(target))
    assert [f.read32(f.player+0xd8),f.read32(f.player+0xdc)]==list(SHOP_IDENTITY)
    own=InteractionFixture(binary);own.write32(own.player+0x84,1)
    own.receive(0x52b5aa,actor_target_reply(dict(target, target=(1,1))))
    assert [own.read32(own.player+0xd8),own.read32(own.player+0xdc)]==[1,1]
    assert own.read32(own.player+0x84)==1
    f.uc.mem_write(grid,struct.pack('<ii',*SHOP_GRID))
    # Initialized pending-command container and native actor identity are input fixtures.
    f.invoke(0x522bd0,(*SHOP_IDENTITY,grid,f.world_state+0xa0,0,0,1),this=0x10d8000)
    c6=parse_npc_request(f.sent[-1]);assert c6['identity']==(1,1) and c6['target']==SHOP_IDENTITY and c6['grid']==SHOP_GRID
    c6['request_id']=123
    f.write32(f.world_state+0xa8,1) # fixture: an issued selection query awaits its server answer
    f.receive(0x52cc40,npc_selection_reply(c6))
    c8=parse_npc_request(f.sent[-1]);assert c8['opcode']==0xc8 and c8['action']==2
    assert c8['identity']==(1,1) and c8['target']==SHOP_IDENTITY and f.disposals==1
    f=InteractionFixture(binary)
    f.receive(0x52cc40,npc_selection_reply(c6));assert not f.sent # no pending selection, no UI action
    f=InteractionFixture(binary);notice=shop_open_notice((1,1),0x70000001)
    f.receive(0x52d561,notice)
    assert f.shop_parse_result==1 and f.opened
    assert [f.read32(f.shop+0x100),f.read32(f.shop+0x104)]==list(SHOP_IDENTITY)
    ack=f.sent[-1];assert len(ack)==36 and struct.unpack_from('<H',ack,1)[0]==0xd7
    assert struct.unpack_from('<IIIII',ack,12)==(1,1,LOCAL_MAP_ID,*SHOP_IDENTITY)
    assert struct.unpack_from('<I',ack,32)[0]==1
    assert not f.assertions
    return {'passed':True,'native_target_selection':target,'native_actor_target':list(SHOP_IDENTITY),'native_self_target_owner_preserved':True,'native_c6':c6,'native_c8':c8,'native_empty_shop_parse_result':f.shop_parse_result,
            'native_shop_identity':[f.read32(f.shop+0x100),f.read32(f.shop+0x104)],'native_d7_hex':ack.hex(),
            'limitations':['Collection lookups, pending-query transport/lifetime and graphical menu/control boundaries substituted',
                           'Original packet field reads, action switches, C8 and D7 construction execute unchanged',
                           'Only empty catalog; does not prove Windows picking, rendered UI, item purchase or full gameplay']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    result=run(a.binary);Path(a.out).write_text(json.dumps(result,indent=2));print('ORIGINAL_NPC_INTERACTION_AND_EMPTY_SHOP_PARSE_PASS')
