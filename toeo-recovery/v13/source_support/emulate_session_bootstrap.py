"""Execute original x86 session dispatcher/allocator in an isolated fixture.

Only CRT heap allocation and security-cookie checks are substituted. Windows,
graphics, sockets and account authorization are not emulated by this test.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UcError
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_EIP
from native_handshake_packets import bootstrap402, add_user401, user_record

EXPECTED_SHA256 = '635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'


class NativeFixture:
    def __init__(self, binary):
        raw = Path(binary).read_bytes()
        if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
            raise ValueError('This address map is only valid for the preserved original binary')
        pe = pefile.PE(data=raw)
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        image = pe.get_memory_mapped_image()
        self.uc.mem_map(0x400000, 0x420000)
        self.uc.mem_write(0x400000, image)
        self.uc.mem_map(0x1000000, 0x400000)
        self.uc.mem_map(0x2000000, 0x100000)
        self.conn, self.table, self.net, self.member = 0x1000000, 0x1001000, 0x1002000, 0x1003000
        self.packet, self.stop = 0x1004000, 0x100f000
        self.heap = 0x1100000
        self.events, self.assertions = [], []
        self.write32(self.conn+8, self.table)
        self.write32(self.conn+0x14, 64)  # registry capacity, allocated by startup in real client
        self.write32(self.conn+0x18, 12)  # inline member adapter follows the 0x44-byte user
        self.write32(self.conn+0x34, self.net)
        self.write32(self.conn+0x58, 1)
        self.write32(self.conn+0x60, 1)  # still connecting before server list
        self.write32(self.net+0x20, self.member)
        self.write32(self.member+4, 1)  # member object supplied by startup
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)

    def write32(self, address, value):
        self.uc.mem_write(address, struct.pack('<I', value))

    def read32(self, address):
        return struct.unpack('<I', self.uc.mem_read(address, 4))[0]

    def ret(self, value=0, cleanup=0):
        sp = self.uc.reg_read(UC_X86_REG_ESP)
        target = self.read32(sp)
        self.uc.reg_write(UC_X86_REG_EAX, value & 0xffffffff)
        self.uc.reg_write(UC_X86_REG_ESP, sp+4+cleanup)
        self.uc.reg_write(UC_X86_REG_EIP, target)

    def on_code(self, uc, address, size, _):
        if address == self.stop:
            uc.emu_stop()
        elif address == 0x5f0be1:  # CRT allocation; does not create or assign a session
            n = self.read32(uc.reg_read(UC_X86_REG_ESP)+4)
            p = self.heap
            self.heap += (n+15)&~15
            self.events.append({'event':'heap_allocate','bytes':n,'result':hex(p)})
            self.ret(p)
        elif address == 0x6baa0d:  # __security_check_cookie, no stack arguments
            self.ret(uc.reg_read(UC_X86_REG_EAX))
        elif address == 0x5f20f0:  # preserve evidence of failed native assertions
            sp = uc.reg_read(UC_X86_REG_ESP)
            self.assertions.append({'line':self.read32(sp+20),'condition_address':hex(self.read32(sp+12)),
                                    'instruction':hex(address)})
            self.ret()
        elif address in (0x60bd20, 0x617ad0):
            sp = uc.reg_read(UC_X86_REG_ESP)
            count = 4 if address == 0x60bd20 else 5
            self.events.append({'event':'native_registration','instruction':hex(address),
                                'args':[hex(self.read32(sp+4+i*4)) for i in range(count)]})
        elif address == 0x617bf1:
            self.events.append({'event':'native_owner_store','instruction':hex(address)})

    def dispatch(self, packet):
        self.uc.mem_write(self.packet, packet)
        self.write32(self.conn+0x80, 4096)  # capacity, not the size of this frame
        sp = 0x20ff000
        self.uc.mem_write(sp, struct.pack('<III', self.stop, self.packet, 0x8002))
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.reg_write(UC_X86_REG_ECX, self.conn)
        try:
            self.uc.emu_start(0x612430, self.stop, count=100000)
        except UcError as exc:
            raise RuntimeError(f'{exc} at EIP={self.uc.reg_read(UC_X86_REG_EIP):x}') from exc
        if self.uc.reg_read(UC_X86_REG_EIP) != self.stop:
            raise RuntimeError('Instruction limit reached before returning')
        owner = self.read32(self.conn+0xc)
        return {'result':hex(self.uc.reg_read(UC_X86_REG_EAX)),
                'owner':hex(owner),'registered_users':self.read32(self.conn+4),
                'own_net_uid':self.read32(self.conn+0x38),
                'owner_adapter':hex(self.read32(owner+0x34)) if owner else None,
                'owner_game_member':hex(self.read32(owner+0x38)) if owner else None,
                'assertions':list(self.assertions),'events':list(self.events)}

    def scan(self, packet):
        self.uc.mem_write(self.packet, packet)
        self.write32(self.conn+0x80, 4096)
        out_skip, out_packet = 0x1005000, 0x1005010
        sp = 0x20ff000
        self.uc.mem_write(sp, struct.pack('<IIIII', self.stop, self.packet, len(packet), out_skip, out_packet))
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.reg_write(UC_X86_REG_ECX, self.conn)
        self.uc.emu_start(0x60ce60, self.stop, count=100000)
        if self.uc.reg_read(UC_X86_REG_EIP) != self.stop:
            raise RuntimeError('Scanner did not return')
        return {'status':self.uc.reg_read(UC_X86_REG_EAX),
                'skip':self.read32(out_skip),'packet_found':hex(self.read32(out_packet)),
                'assertions':list(self.assertions)}


def run(binary):
    cases = {}
    cases['old401_without_owner'] = NativeFixture(binary).dispatch(add_user401())
    cases['old402_zero_rows'] = NativeFixture(binary).dispatch(bootstrap402(records=[]))
    cases['402_nonself_row'] = NativeFixture(binary).dispatch(
        bootstrap402(records=[user_record(member_id=2,net_uid=2)]))
    fixture = NativeFixture(binary)
    cases['402_self_row'] = fixture.dispatch(bootstrap402())
    fixture.write32(fixture.conn+0x60, 0x8002)  # sender transitions here after observing own session
    cases['401_after_bootstrap'] = fixture.dispatch(add_user401())
    assert cases['old401_without_owner']['owner'] == '0x0'
    assert cases['old401_without_owner']['result'] == '0xffffffff'
    assert cases['old402_zero_rows']['owner'] == '0x0'
    assert cases['402_nonself_row']['owner'] == '0x0'
    assert cases['402_self_row']['owner'] != '0x0'
    assert cases['402_self_row']['owner_game_member'] == hex(fixture.member)
    assert cases['402_self_row']['own_net_uid'] == 1
    assert cases['401_after_bootstrap']['result'] == '0x1'
    assert cases['401_after_bootstrap']['registered_users'] == 2
    assert all(not c['assertions'] for c in cases.values())
    scanners = {}
    packet = bootstrap402()
    scanners['exact64'] = NativeFixture(binary).scan(packet)
    scanners['coalesced_with_next_byte'] = NativeFixture(binary).scan(packet+b'\x00')
    bad = bytearray(packet+b'\x00'); bad[-5] = 0
    scanners['bad_tail'] = NativeFixture(binary).scan(bytes(bad))
    assert scanners['exact64']['status'] == 1
    assert scanners['coalesced_with_next_byte']['status'] == 2
    assert scanners['bad_tail']['status'] == 0
    assert all(not c['assertions'] for c in scanners.values())
    return {'original_sha256':EXPECTED_SHA256,'level':'isolated_original_x86_session_code',
            'does_not_prove':['Windows graphical runtime','account authentication','character list','playable world'],
            'substitutions':['CRT allocation','security cookie check','assertion logger (none triggered)'],
            'fixture':'Startup connection, registry, network and member object scaffolding',
            'cases':cases,'scanner_cases':scanners,'passed':True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('binary')
    parser.add_argument('--out',required=True)
    args = parser.parse_args()
    result = run(args.binary)
    Path(args.out).write_text(json.dumps(result,indent=2),encoding='utf-8')
    for name, case in result['cases'].items():
        print(name, 'result='+case['result'], 'owner='+case['owner'],
              'registered='+str(case['registered_users']), 'assertions='+str(len(case['assertions'])))
    print('ORIGINAL_X86_SESSION_TEST_PASS')
