"""Verify original 0x14 query and header-only 0x15 correlator, without map claims."""
import argparse,json
from pathlib import Path
from emulate_account_transport import TransportFixture
from account_packets import message
from native_data_packets import data405,parse405
from emulate_session_bootstrap import EXPECTED_SHA256

def verify_query(binary,request_op,answer_op):
    f=TransportFixture(binary);packet,query=0x109b000,0x109b100
    f.uc.mem_write(packet,message(request_op,b'',0xffffffff))
    f.invoke(0x435560,(packet,query,1),this=f.wrapper)
    request=parse405(f.frames[-1])['payload']
    assert request==message(request_op,b'',1)
    assert f.read32(query+8)==f.info
    def status():return bytes(f.uc.mem_read(f.info+0x14,1))[0]
    cases={'pending':status()}
    for name,op,req in [('wrong_id',answer_op,2),('unmatched_opcode',0x16,1),('matched',answer_op,1)]:
        f.dispatch(data405(message(op,b'',req),0,2,1,1));cases[name]=status()
    assert cases==dict(pending=1,wrong_id=1,unmatched_opcode=1,matched=2)
    assert not f.assertions
    return dict(passed=True,original_sha256=EXPECTED_SHA256,request_hex=request.hex(),cases=cases,
                level='original enqueue/frame/receive/query correlation',
                limitations=['Transport fixture scaffolding and OS/CRT boundaries','Does not execute GUI relogin or load maps'])
def run(binary):
    return verify_query(binary,0x14,0x15)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    Path(a.out).write_text(json.dumps(run(a.binary),indent=2));print('ORIGINAL_WORLD_RELOGIN_ACK_PASS')
