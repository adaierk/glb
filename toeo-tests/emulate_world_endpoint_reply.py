"""Execute original endpoint parser through descriptor copy, recording socket boundary."""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP
from emulate_world_completion import CompletionFixture
from world_endpoint_packets import endpoint_reply
from emulate_session_bootstrap import EXPECTED_SHA256

class EndpointFixture(CompletionFixture):
    def __init__(self,binary):
        super().__init__(binary);self.endpoint_calls=[]
    def on_code(self,uc,va,size,x):
        if va==0x61be40:
            sp=uc.reg_read(UC_X86_REG_ESP)
            args=[self.read32(sp+i) for i in range(4,28,4)]
            self.endpoint_calls.append(dict(mode=args[0],ip=args[1],tcp_port=args[2],peer_port=args[3],
                                           endpoint=bytes(uc.mem_read(args[4],6)).hex(),nonce=args[5]))
            self.ret(0,24) # socket lifecycle boundary only; no simulated ready state
        else:super().on_code(uc,va,size,x)

def run(binary):
    f=EndpointFixture(binary);packet=0x109b000
    answer=endpoint_reply(b'ABCDEF',11101,11101,3,1,0x123abc,0x0100007f,1)
    f.uc.mem_write(packet,answer);f.invoke(0x61ec50,(packet,0))
    raw=bytes(f.uc.mem_read(f.login+0x58,28))
    assert raw==struct.pack('<IIIIII',1,1,11101,3,11101,1)+bytes.fromhex('7f000001')
    assert f.endpoint_calls==[dict(mode=1,ip=0x0100007f,tcp_port=11101,peer_port=12101,
                                   endpoint='414243444546',nonce=0x123abc)]
    assert not f.assertions
    return dict(passed=True,original_sha256=EXPECTED_SHA256,answer_hex=answer.hex(),
                native_descriptor_hex=raw.hex(),endpoint_calls=f.endpoint_calls,
                level='original 61ec50 field extraction, reset and 61ae30 descriptor copy',
                limitations=['Inherited transport/CRT fixture','61be40 socket lifecycle substituted at call boundary',
                             'No real socket startup, Windows world connection or map success inferred'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    Path(a.out).write_text(json.dumps(run(a.binary),indent=2));print('ORIGINAL_WORLD_ENDPOINT_REPLY_PARSER_PASS')
