"""Execute original account request, cipher and result handler, with declared transport fixture."""
import argparse
import json
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_EIP
from emulate_session_bootstrap import NativeFixture, EXPECTED_SHA256
from native_handshake_packets import bootstrap402
from account_packets import login_request, login_ok_body, message, decode_string


class AccountFixture(NativeFixture):
    def __init__(self, binary, bootstrap=None):
        super().__init__(binary)
        self.login, self.wrapper, self.info, self.answer = 0x1010000, 0x1011000, 0x1012000, 0x1013000
        self.captured = []
        self.dispatch(bootstrap if bootstrap is not None else bootstrap402())
        self.write32(self.wrapper+4, self.conn)
        self.write32(self.login+8, self.wrapper)
        self.write32(self.login+0x118, 2)  # fixture: upstream connection has reached ready stage

    def on_code(self, uc, address, size, _):
        if address == 0x5f0bbc:
            n = self.read32(uc.reg_read(UC_X86_REG_ESP)+4)
            p = self.heap; self.heap += (n+15)&~15
            self.events.append({'event':'heap_allocate','bytes':n,'result':hex(p)})
            self.ret(p)
        elif address == 0x435560:
            sp = uc.reg_read(UC_X86_REG_ESP)
            p = self.read32(sp+4)
            size = struct.unpack('<H', uc.mem_read(p+3,2))[0]
            self.captured.append(bytes(uc.mem_read(p,size)))
            self.events.append({'event':'transport_boundary_capture','instruction':hex(address),'bytes':size})
            self.ret(1,12)  # successful enqueue, NOT authentication
        elif address in (0x61b2a0, 0x61dbac):
            self.events.append({'event':'native_login_result' if address == 0x61b2a0 else 'native_login_success_store',
                                'instruction':hex(address)})
        else:
            super().on_code(uc,address,size,_)

    def invoke(self, address, args=(), this=None):
        sp = 0x20ff000
        self.uc.mem_write(sp,struct.pack('<'+'I'*(len(args)+1),self.stop,*args))
        self.uc.reg_write(UC_X86_REG_ESP,sp)
        self.uc.reg_write(UC_X86_REG_ECX,self.login if this is None else this)
        self.uc.emu_start(address,self.stop,count=200000)
        if self.uc.reg_read(UC_X86_REG_EIP) != self.stop:
            raise RuntimeError('Native function did not return')

    def request(self, username='archive001', password='local123'):
        user, pw = 0x1014000, 0x1015000
        self.uc.mem_write(user,username.encode('cp932')+b'\x00')
        self.uc.mem_write(pw,password.encode('cp932')+b'\x00')
        self.invoke(0x620d80,(user,pw))
        assert self.captured[-1] == login_request(username,password)
        assert self.read32(self.login+0x18) == 2
        return self.captured[-1]

    def deliver(self, reply, transport_status=2):
        self.uc.mem_write(self.answer,reply)
        self.uc.mem_write(self.info+0x14,bytes([transport_status]))
        self.write32(self.info+0x34,self.answer)
        self.write32(self.login+0xc0,self.info)  # fixture: transport completed this request
        self.invoke(0x61d9e0)
        result = self.read32(self.login+0x20)
        status = self.read32(self.login+0x18)
        return {'status':status if status < 0x80000000 else status-0x100000000,
                'result_pointer':hex(result),
                'account_id':self.read32(result+0x48) if result else None,
                'login_sid':self.read32(result+0x4c) if result else None,
                'username':decode_string(bytes(self.uc.mem_read(result,70))) if result else None,
                'assertions':list(self.assertions),'events':list(self.events)}


def run(binary):
    cases = {}
    f = AccountFixture(binary); request = f.request()
    # Message code is irrelevant to this isolated handler; routing tested separately.
    cases['matching_uid_and_sid'] = f.deliver(message(0x21,login_ok_body()))
    f = AccountFixture(binary); f.request()
    cases['wrong_uid_rejected'] = f.deliver(message(0x21,login_ok_body(net_uid=2)))
    f = AccountFixture(binary); f.request()
    cases['transport_failure'] = f.deliver(b'\x00'*99,transport_status=3)
    for user,pw in [('abc','def'),('a'*64,'z'*64),('テスト','ローカル')]:
        f = AccountFixture(binary); f.request(user,pw)
        assert not f.assertions
    assert cases['matching_uid_and_sid']['status'] == 1
    assert cases['matching_uid_and_sid']['account_id'] == 1
    assert cases['matching_uid_and_sid']['login_sid'] == 1
    assert cases['wrong_uid_rejected']['status'] == -15
    assert cases['transport_failure']['status'] == -16
    assert all(not c['assertions'] for c in cases.values())
    return {'original_sha256':EXPECTED_SHA256,'passed':True,'level':'isolated_original_x86_account_code',
            'request_hex':request.hex(),'cases':cases,
            'substitutions':['CRT allocations','security cookie','assertion logger (none triggered)',
                             '435560 transport enqueue returns success and captures native payload'],
            'fixture':['Network session created by real bootstrap handler','upstream ready stage 2',
                       'transport result object supplied directly; cleanup wrapper has no network module'],
            'does_not_prove':['Reply opcode routing','socket transport','Windows GUI','character selection','playable world']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('binary'); p.add_argument('--out',required=True)
    a = p.parse_args(); result = run(a.binary)
    Path(a.out).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print('ORIGINAL_X86_ACCOUNT_HANDLER_PASS')
    print(json.dumps({k:v['status'] for k,v in result['cases'].items()}))
