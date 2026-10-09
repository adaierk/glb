"""Original world broadcast-wrapper ACK correlation, including negative controls.

Uses the original 7085e4 vtable installed by native constructor 621dea.
No request completion flags are patched by the fixture.
"""
import argparse,json
from pathlib import Path
from emulate_world_completion import CompletionFixture
from native_data_packets import data405
from account_packets import message

class BroadcastFixture(CompletionFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.write32(0x6e27fc,0x100f100)
    def on_code(self,uc,address,size,extra):
        if address==0x100f100:
            self.ret(1000) # Declared Windows GetTickCount boundary.
        else:
            super().on_code(uc,address,size,extra)

def run(binary):
    f=BroadcastFixture(binary)
    f.request_admission();f.accept_admission()
    f.write32(f.upstream['wrapper'],0x7085e4)
    f.request_attachment()
    cases={}
    for label,opcode,request_id,channel in [
        ('wrong_account_wrapper_ack',0x11,2,f.upstream),
        ('wrong_request_id',5,3,f.upstream),
        ('wrong_channel',5,2,f.world),
        ('matched_broadcast_ack',5,2,f.upstream)]:
        f.dispatch_channel(data405(message(opcode,b'',request_id),0,2,1,1),channel)
        cases[label]=f.advance()
        assert cases[label]['stage']==(9 if label=='matched_broadcast_ack' else 8)
    assert cases['matched_broadcast_ack']['result']==2 and not f.assertions
    return dict(passed=True,wrapper_vtable='0x7085e4',receive_dispatch='0x61fc50',
                account_query_opcode=4,account_ack_opcode=5,cases=cases,
                limitations=['Native transport fixture; Windows execution and map rendering require separate evidence'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();r=run(a.binary);Path(a.out).write_text(json.dumps(r,indent=2))
    print('ORIGINAL_WORLD_BROADCAST_COMPLETION_PASS')
