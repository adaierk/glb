"""Execute original EE / 4D7DB0 source attributes, NAME and description readers.

Item-source container insertion/lookup and empty source constructor are fixture
boundaries. Record traversal, attributes, icon number and text parsing are native.
"""
import argparse,json
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX
from emulate_item_use import UseFixture
from world_item_source_packets import parse_item_source_request,item_source_reply
from world_shop_catalog import historical_stock,PREVIEW_SOURCE_KEY


class SourceFixture(UseFixture):
    def __init__(self,binary):
        self.sources={};super().__init__(binary);self.manager=0x10e9000

    def on_code(self,uc,va,size,context):
        sp=uc.reg_read(UC_X86_REG_ESP);obj=uc.reg_read(UC_X86_REG_ECX)
        if va==0x4db420:self.ret(self.sources.get(self.read32(sp+4),0),4)
        elif va==0x4d7c90:
            uc.mem_write(obj,bytes(0x1d0));self.item_strings[obj+8+0x34]='';self.ret(obj)
        elif va==0x4d7100 and obj==self.manager:
            pair=self.read32(sp+8);self.sources[self.read32(pair)]=self.read32(pair+4);self.ret(self.read32(sp+4),8)
        elif va==0x4f14b0 and obj==self.manager+12:
            self.write32(self.read32(sp+4),0);self.ret(self.read32(sp+4),8)
        else:super().on_code(uc,va,size,context)


def run(binary):
    f=SourceFixture(binary)
    request=parse_item_source_request(bytes.fromhex('80ed0024002c000000000000240000000801120101000000010000000100000001000000'))
    payload=item_source_reply(request,historical_stock(PREVIEW_SOURCE_KEY)['stock'])
    f.uc.mem_write(f.buffer,payload);f.invoke(0x4d7db0,(f.buffer,),this=f.manager)
    item=f.sources[1];name=f.item_strings[item+8+0x34];description=f.item_strings[item+0x13c]
    assert name=='レモングミ' and description=='HP 300 / TP 0' and f.read32(item+8+0x30)==3811 and not f.assertions
    return {'passed':True,'native_name':name,'native_description':description,'native_icon_id':3811,
        'request':request,'assertions':f.assertions,'substitutions':['Empty source C++ constructor','Source and list container boundaries',
            'Inherited item-use fixture boundaries'],'limitations':['Original Windows item-detail control still needs separate validation']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    result=run(a.binary);Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ORIGINAL_ITEM_SOURCE_NAME_ICON_DESCRIPTION_PASS')
