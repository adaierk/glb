"""Original selection parser -> ticket setter -> admission builder; explicit endpoint boundary."""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESI,UC_X86_REG_ESP,UC_X86_REG_EIP
from emulate_character_select import SelectFixture
from character_packets import select_character_reply
from world_auth_packets import world_admission_request,world_admission_ack
from native_data_packets import data405

class HandoffFixture(SelectFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.attach_request=None
    def on_code(self,uc,address,size,extra):
        if address==0x43d2c0:
            sp=uc.reg_read(UC_X86_REG_ESP)
            self.attach_request=bytes(uc.mem_read(self.read32(sp+8),13))
            self.attach_route=self.read32(sp+4)
            uc.emu_stop() # broadcast transport endpoint deliberately not substituted with success
        else:super().on_code(uc,address,size,extra)
    def handoff(self):
        holder=0x1070000;self.write32(holder+0x10,self.login)
        self.write32(self.login+0x3c,0);self.write32(self.login+0x2c,0xffffffff)
        self.write32(self.login+0xc,0);self.write32(self.login+0x10,0)
        self.uc.reg_write(UC_X86_REG_ESI,self.selected)
        self.uc.reg_write(UC_X86_REG_ECX,holder)
        self.uc.reg_write(UC_X86_REG_ESP,0x20ff000)
        self.uc.emu_start(0x43edc2,0x43edce,count=200000)
        assert self.uc.reg_read(UC_X86_REG_EIP)==0x43edce
        assert self.read32(self.login+0x2c)==2 and not self.assertions
        return self.read32(self.login+0x3c)
    def admission(self):
        # Explicit unverified socket startup boundary: stage 2..4 is not executed.
        self.write32(self.login+4,self.wrapper);self.write32(self.login+0x2c,5)
        self.write32(self.net+0xf4,11100)
        self.invoke(0x620760)
        payload=self.frames[-1][36:-4]
        assert payload==world_admission_request(11100,self.read32(self.login+0x3c)&0xffff,2)
        self.dispatch(data405(world_admission_ack(2),0,2,1,1));self.invoke(0x620760)
        assert self.read32(self.login+0x2c)==7 and not self.assertions
        return payload
    def account_attachment(self,account_id,sid):
        result=0x1071000;self.write32(self.login+0x20,result)
        self.write32(result+0x48,account_id);self.write32(result+0x4c,sid)
        self.uc.reg_write(UC_X86_REG_ESP,0x20ff000)
        self.uc.mem_write(0x20ff000,struct.pack("<I",self.stop))
        self.uc.reg_write(UC_X86_REG_ECX,self.login)
        self.uc.emu_start(0x620760,self.stop,count=200000)
        assert self.uc.reg_read(UC_X86_REG_EIP)==0x43d2c0
        assert self.attach_request is not None
        assert struct.unpack_from('<I',self.attach_request,9)[0]==account_id
        assert struct.unpack_from('<H',self.attach_request,1)[0]==4
        assert self.read32(self.login+0x2c)==7 # stopped before broadcast call, not completed
        return {'opcode':4,'bytes':13,'body_account_id':account_id,'distinct_login_sid':sid,
                'hex':self.attach_request.hex(),'destination':hex(self.attach_route),
                'boundary':'before original 43d2c0 broadcast send; no ACK or stage-8 success claimed'}

def run(binary):
    cases={}
    for ticket in (1,54321,65535):
        f=HandoffFixture(binary);f.request_selection()
        selected=f.receive_selection(select_character_reply((ticket,0,123,456,0,0,0,0,0),[(0x0100007f,45002,11101)]))
        actual=f.handoff();assert actual==ticket
        request=f.admission();attach=f.account_attachment(47,0x123abc)
        cases[str(ticket)]={'selected':selected['branch'],'native_ticket':actual,'native_initial_stage':2,
                            'admission_hex':request.hex(),'ack_stage':7,'attachment':attach,'assertions':f.assertions}
    return {'passed':True,'cases':cases,'executed':['original 437da0 selection parser','original 43edc2 ticket transfer and 61ba60 setter','original 620760 admission builder and ACK wait','original 620760 account-ID request builder / 61b090 getter'],
            'limitations':['Selection/task startup scaffolding','Stage 2..4 socket setup bypassed explicitly','0x04 stopped before broadcast transport','Unconfirmed remaining selection fields use research values','No Windows GUI, map or playability']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    r=run(a.binary);Path(a.out).write_text(json.dumps(r,indent=2));print('ORIGINAL_WORLD_TICKET_HANDOFF_AND_ACCOUNT_ID_PASS')
