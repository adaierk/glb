"""Original world admission builder, wire path, 19 ACK and controller 6->7.

Fixture starts at world controller stage 5, after prior endpoint setup; this
does not prove endpoint startup or continuous Windows world connection.
"""
import argparse
import json
from pathlib import Path
from emulate_account_transport import TransportFixture
from world_auth_packets import world_admission_request,world_admission_ack
from native_data_packets import data405


class AdmissionFixture(TransportFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.write32(self.login+4,self.wrapper)
        self.write32(self.login+0x2c,5)  # isolated stage entry, not original startup proof
        self.write32(self.login+0x30,1)
        self.write32(self.net+0xf4,11100)  # original getter 445ee0(network, index=0)

    def request_admission(self,ticket=54321):
        self.write32(self.login+0x3c,ticket)
        self.invoke(0x620760)
        p=self.frames[-1][36:-4]
        assert p==world_admission_request(11100,ticket,1)
        assert self.read32(self.login+0x2c)==6
        assert self.read32(self.login+0x84)==self.info
        return p

    def receive_ack(self,request_id=1):
        self.dispatch(data405(world_admission_ack(request_id),0,2,1,1))
        return self.advance_after_reply()

    def advance_after_reply(self):
        transport=bytes(self.uc.mem_read(self.info+0x14,1))[0]
        self.invoke(0x620760)
        return {'request_status':transport,'world_controller_stage':self.read32(self.login+0x2c),
                'world_controller_result':self.read32(self.login+0x30),'assertions':self.assertions}


def run(binary):
    f=AdmissionFixture(binary);p=f.request_admission();good=f.receive_ack()
    w=AdmissionFixture(binary);w.request_admission();wrong=w.receive_ack(2)
    assert good['request_status']==2 and good['world_controller_stage']==7
    assert wrong['request_status']==1 and wrong['world_controller_stage']==6
    assert not good['assertions'] and not wrong['assertions']
    return {'passed':True,'request_hex':p.hex(),'cases':{'matched_ack':good,'wrong_request_id':wrong},
            'level':'original_world_18_builder_NNet_send_receive_ACK_correlation_controller_6_to_7',
            'fixture':['World controller stage 5 and result 1; ready endpoint wrapper scaffolding',
                       'Inherited supported plain TCP mode and CRT/clock/socket boundaries'],
            'does_not_prove':['ticket issuing in original server','prior world endpoint setup','later SID/session attachment',
                             'map loading','Windows GUI','playability']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();r=run(a.binary)
    Path(a.out).write_text(json.dumps(r,indent=2),encoding='utf-8')
    print('ORIGINAL_X86_WORLD_ADMISSION_ACK_PASS')
