"""Original world admission and account-control completion with distinct native channels.

Starts at stage 5 after unverified world socket startup. Does not fake ACK status.
"""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESP
from emulate_account_transport import TransportFixture
from native_handshake_packets import bootstrap402,user_record
from native_data_packets import data405
from account_packets import message
from world_auth_packets import world_admission_request,world_admission_ack,world_account_request

class CompletionFixture(TransportFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.channel_frames=[]
        self.upstream={'conn':self.conn,'wrapper':self.wrapper,'module':self.module,'info':self.info}
        self.world=self.add_world_channel()
        self.write32(self.login+4,self.upstream['wrapper'])
        self.write32(self.login+8,self.world['wrapper'])
        self.write32(self.login+0x2c,5);self.write32(self.login+0x30,1)
        self.write32(self.net+0xf4,11100)
        self.result=0x1071000
        self.write32(self.login+0x20,self.result)
        self.write32(self.result+0x48,47);self.write32(self.result+0x4c,0x123abc)
    def on_code(self,uc,address,size,extra):
        if address==0x60c950 and hasattr(self,'channel_frames'):
            sp=uc.reg_read(UC_X86_REG_ESP)
            p,n=self.read32(sp+8),self.read32(sp+12)
            conn=uc.reg_read(UC_X86_REG_ECX)
            self.channel_frames.append({'conn':conn,'wire':bytes(uc.mem_read(p,n))})
        super().on_code(uc,address,size,extra)
    def add_world_channel(self):
        conn,table,net,member=0x1080000,0x1081000,0x1082000,0x1083000
        module,info,wrapper=0x1084000,0x1085000,0x1086000
        self.write32(conn+8,table);self.write32(conn+0x14,64);self.write32(conn+0x18,12)
        self.write32(conn+0x34,net);self.write32(conn+0x58,1);self.write32(conn+0x60,1)
        self.write32(net+0x20,member);self.write32(member+4,1)
        old=self.conn;self.conn=conn
        try:self.dispatch(bootstrap402(records=[user_record(2,2,1),user_record(1,1,2)]))
        finally:self.conn=old
        self.write32(wrapper,0x708614);self.write32(wrapper+4,conn);self.write32(wrapper+8,module)
        self.write32(wrapper+0x10,self.login);self.write32(wrapper+0x34,0x1087000)
        self.write32(wrapper+0x38,4096);self.write32(wrapper+0x3c,1024);self.write32(wrapper+0x40,1024)
        self.write32(wrapper+0x44,0x622960);self.write32(wrapper+0x4c,0x622ac0)
        self.write32(module+8,info);self.write32(module+0x20,module+0x20);self.write32(module+0x24,module+0x20)
        self.write32(module+0x28,conn);self.write32(module+0x3c,1)
        self.write32(net,1);self.write32(conn+0x58,4096);self.write32(conn+0x7c,0x1088000)
        self.write32(conn+0x80,4096);self.write32(conn+0x88,0x622870);self.write32(conn+0x8c,wrapper)
        self.write32(conn+0x90,0x622890);self.write32(conn+0x94,wrapper)
        self.write32(conn+0x194,conn+0x1c0)
        self.write32(self.read32(conn+0xc)+0x2c,0x1089000)
        self.write32(conn+0xb0,0x8002);self.write32(conn+0xf8,1000)
        self.invoke(0x615dd0,(0,),this=conn)
        assert self.read32(conn+0x60)==0x8002 and not self.assertions
        return {'conn':conn,'wrapper':wrapper,'module':module,'info':info}
    def dispatch_channel(self,wire,channel):
        old=self.conn;self.conn=channel['conn']
        try:self.dispatch(wire)
        finally:self.conn=old
    def request_admission(self,ticket=54321):
        self.write32(self.login+0x3c,ticket);self.invoke(0x620760)
        entry=self.channel_frames[-1];payload=entry['wire'][36:-4]
        assert entry['conn']==self.world['conn']
        assert payload==world_admission_request(11100,ticket,1)
        assert self.read32(self.login+0x84)==self.world['info']
        return entry['wire']
    def accept_admission(self,wire=None):
        self.dispatch_channel(wire or data405(world_admission_ack(1),0,2,1,1),self.world)
        self.invoke(0x620760);assert self.read32(self.login+0x2c)==7
    def request_attachment(self):
        self.invoke(0x620760)
        entry=self.channel_frames[-1];payload=entry['wire'][36:-4]
        assert entry['conn']==self.upstream['conn']
        assert payload==world_account_request(self.read32(self.result+0x48),2)
        assert self.read32(self.login+0xcc)==self.upstream['info']
        assert self.read32(self.login+0x2c)==8 and not self.assertions
        return entry['wire']
    def advance(self):
        self.invoke(0x620760)
        return {'stage':self.read32(self.login+0x2c),'result':self.read32(self.login+0x30),
                'upstream_request_status':bytes(self.uc.mem_read(self.upstream['info']+0x14,1))[0],
                'assertions':self.assertions}

def run(binary):
    f=CompletionFixture(binary);admission=f.request_admission();f.accept_admission();attach=f.request_attachment()
    cases={}
    for name,op,req,channel in [('wrong_channel',0x11,2,f.world),('wrong_id',0x11,3,f.upstream),('ignored_opcode_05',5,2,f.upstream),('matched_11',0x11,2,f.upstream)]:
        f.dispatch_channel(data405(message(op,b'',req),0,2,1,1),channel);cases[name]=f.advance()
        assert cases[name]['stage']==(9 if name=='matched_11' else 8)
    assert cases['matched_11']['result']==2 and not f.assertions
    return {'passed':True,'admission_hex':admission[36:-4].hex(),'attachment_hex':attach[36:-4].hex(),
            'distinct_channels':{'admission':'controller+8 world wrapper/pool','account_control':'controller+4 upstream wrapper/pool'},
            'cases':cases,'level':'original distinct-channel send_receive_correlation_controller_5_to_9',
            'limitations':['Starts at stage 5 after socket setup','Supported plain TCP fixture','0x11 is measured compatible correlator ACK, not evidence of historical server implementation','No Windows event loop, UDP startup, map or playability']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    r=run(a.binary);Path(a.out).write_text(json.dumps(r,indent=2));print('ORIGINAL_DISTINCT_CHANNEL_WORLD_COMPLETION_PASS')
