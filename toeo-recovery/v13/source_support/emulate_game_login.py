"""Original game prelogin request and native UI identity/UID acceptance checks.

Result validation starts at the normal completed-transport branch (449289).
The original packet filter executes; the MFC event loop after acceptance does not.
"""
import argparse
import json
import struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBX,UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_ESP,UC_X86_REG_EIP
from emulate_account_transport import TransportFixture
from game_login_packets import game_login_request,game_login_reply
from account_packets import encode_string,decode_string


class GameFixture(TransportFixture):
    def __init__(self,binary,username='archive001',password='local123'):
        super().__init__(binary)
        self.ui,self.fields,self.global_root,self.global_frame,self.parts=0x1030000,0x1031000,0x1032000,0x1033000,0x1034000
        self.game,self.config,self.netstate=0x1035000,0x1036000,0x1037000
        self.username,self.password=username,password
        self.write32(0x80dbf4,self.global_root)
        self.write32(self.global_root+0x28,self.global_frame)
        self.write32(self.global_frame+0x28,self.parts)
        self.write32(self.parts+0x2c,self.game)
        self.write32(self.parts+0x30,self.netstate)
        self.write32(self.game+0x24,self.config)
        self.write32(self.game+0x6c,0x1038000)
        self.write32(self.netstate+0x38,self.login)
        counters,dispatch,collection,node=0x103a000,0x103b000,0x103c000,0x103d000
        self.write32(self.netstate+0x54,counters)
        self.write32(self.netstate+0x44,dispatch)
        self.write32(dispatch,collection)
        self.write32(collection+8,node)
        self.write32(node+4,node)
        self.uc.mem_write(node+0x39,b'\x01')
        self.write32(self.wrapper+0x24,0x530600)  # exact first-login game filter installed by 5314ea
        self.write32(self.ui+0x14,self.fields)
        for off,text in ((0x214,username),(0x25a,username),(0x2a0,password)):
            self.uc.mem_write(self.fields+off,encode_string(text))
        self.slice_result=None

    def receive_game_reply(self,reply):
        from native_data_packets import data405
        self.dispatch(data405(reply,0,2,1,1))
        assert bytes(self.uc.mem_read(self.info+0x14,1))==b'\x02'
        assert self.read32(self.info+0x2c)==96
        captured=bytes(self.uc.mem_read(self.read32(self.info+0x34),96))
        assert captured==reply[:96]
        return self.validate_result_slice(captured)

    def on_code(self,uc,address,size,_):
        if address==0x5f4a80:  # UI text log only, no protocol/state effects
            self.ret(0)
        elif address in (0x4493d2,0x4493dc,0x4493e6):
            self.slice_result={'0x4493d2':'accepted','0x4493dc':'identity_or_uid_rejected',
                               '0x4493e6':'server_rejected'}[hex(address)]
            uc.emu_stop()
        elif address in (0x49e780,0x4667d0):
            # UI continuation side effects beyond protocol acceptance; stop before these calls.
            self.slice_result='accepted';uc.emu_stop()
        else:super().on_code(uc,address,size,_)

    def request_game(self):
        self.invoke(0x448fb0,this=self.ui)
        p=self.frames[0][36:-4]
        expected=bytearray(game_login_request(self.username,self.password))
        expected[5:9]=struct.pack('<I',1)
        assert p==bytes(expected)
        assert self.read32(self.ui+0x20)==self.info
        return p

    def validate_result_slice(self,reply):
        self.uc.mem_write(self.answer,reply)
        self.write32(self.info+0x34,self.answer)
        self.uc.reg_write(UC_X86_REG_EAX,self.info)
        self.uc.reg_write(UC_X86_REG_EBP,0x20fe000)
        self.uc.reg_write(UC_X86_REG_ESP,0x20fd000)
        self.uc.reg_write(UC_X86_REG_ESI,self.answer)
        self.uc.reg_write(UC_X86_REG_EDI,self.ui)
        self.uc.reg_write(UC_X86_REG_EBX,0x1038000)
        self.uc.emu_start(0x449289,self.stop,count=200000)
        if self.slice_result is None:raise RuntimeError('Acceptance slice did not reach a known result')
        return {'branch':self.slice_result,'assertions':self.assertions,
                'stored_game_id':decode_string(bytes(self.uc.mem_read(self.config+0x256,70)))
                                 if self.slice_result=='accepted' else None,
                'stored_account_id':self.read32(self.config+0x2e8)}


def run(binary):
    f=GameFixture(binary);request=f.request_game()
    good=f.receive_game_reply(game_login_reply('archive001'))
    f=GameFixture(binary);bad_uid=f.validate_result_slice(game_login_reply('archive001',net_uid=2))
    f=GameFixture(binary);bad_identity=f.validate_result_slice(game_login_reply('wrong'))
    assert good['branch']=='accepted' and good['stored_account_id']==1
    assert bad_uid['branch']=='identity_or_uid_rejected'
    assert bad_identity['branch']=='identity_or_uid_rejected'
    assert not good['assertions'] and not bad_uid['assertions'] and not bad_identity['assertions']
    return {'passed':True,'request_hex':request.hex(),'cases':{'good':good,'wrong_uid':bad_uid,'wrong_identity':bad_identity},
            'level':'original_game_prelogin_builder_NNet_receive_game_filter_correlation_and_identity_validation_slice',
            'substitutions':['same transport/CRT/clock boundaries as account transport fixture','MFC text log'],
            'fixture':['Supported TCP-only plain branch','startup game globals and empty forwarding registry',
                       'native game filter 530600 selected from actual 5314ea configuration'],
            'does_not_prove':['MFC UI continuation','actual Windows startup transport mode','role list','map entry']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();r=run(a.binary);Path(a.out).write_text(json.dumps(r,indent=2),encoding='utf-8')
    print('ORIGINAL_X86_GAME_PRELOGIN_BUILDER_AND_IDENTITY_CHECK_PASS')
