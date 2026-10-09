"""Unchanged native 55 builder, B2 vitality reader and 67 inventory update.

OS time, native world-ready check, transport and inherited UI/container/string
boundaries are substituted. Item identity, opcode, fields, HP/TP clamping and
quantity updates execute original x86. Windows mouse validation is separate.
"""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP
from emulate_inventory_trade import WorldFixture
from world_item_use_packets import parse_item_use_request,vitals_notice
from world_inventory_packets import inventory_notice,transaction_reply,parse_shop_close_request
from world_npc_packets import SHOP_IDENTITY


class UseFixture(WorldFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.profile=0x10e8000;self.write32(self.player+0x114,self.profile)
        self.write32(self.profile+8,40);self.write32(self.profile+12,10)
        self.write32(self.profile+0xa8,100);self.write32(self.profile+0xac,30)

    def on_code(self,uc,va,size,context):
        if va==0x60a3e0:
            sp=uc.reg_read(UC_X86_REG_ESP);p=self.read32(sp+12)
            n=struct.unpack('<H',uc.mem_read(p+3,2))[0]
            self.trade_packets.append(bytes(uc.mem_read(p,n)));self.ret(1,20)
        elif va==0x4c8550:self.ret(1) # initialized native world-ready gate
        else:super().on_code(uc,va,size,context)


def run(binary):
    f=UseFixture(binary);p=0x10e3000;instance=(0x71000001,1,1,0)
    f.uc.mem_write(p,struct.pack('<IIII',*instance))
    f.invoke(0x4f6ce0,(p,2,0,0,1,1),this=f.command)
    built=f.trade_packets[-1];request=parse_item_use_request(built)
    assert request['sequence']==1 and request['item']==instance and request['target']==(1,1) and request['count']==0
    snapshot={'money':4100,'capacity':32,'items':[{'identity':instance,'catalog_index':0,
        'quantity':2,'name':'レモングミ','buy_price':360,'sell_price':180}]}
    f.receive(0x52b8ef,inventory_notice((1,1),0x1110101,snapshot))
    snapshot['items'][0]['quantity']=1;f.write32(f.command+0x10,1)
    f.receive(0x52b86b,transaction_reply(1,4100,request_id=request['request_id'],snapshot=snapshot))
    clone=f.collections[f.inventory][0]
    assert struct.unpack('<h',f.uc.mem_read(clone+0x24,2))[0]==1 and f.read32(clone+0x30)==3811
    assert f.read32(f.command+0x10)==0 and f.read32(f.wallet)==4100
    vitals={'hp':100,'tp':10,'max_hp':100,'max_tp':30}
    f.receive(0x52ca9b,vitals_notice((1,1),0x1110101,vitals))
    actual={'hp':f.read32(f.profile+8),'tp':f.read32(f.profile+12),
        'max_hp':f.read32(f.profile+0xa8),'max_tp':f.read32(f.profile+0xac)}
    assert actual==vitals and not f.assertions
    close=UseFixture(binary);close.uc.mem_write(p,struct.pack('<IIII',*instance))
    close.invoke(0x4f8910,SHOP_IDENTITY,this=close.command)
    close_request=parse_shop_close_request(close.trade_packets[-1])
    assert close_request['sequence']==1 and close_request['merchant']==SHOP_IDENTITY
    # Transport-pending registry is a declared fixture boundary; the original
    # builder's rejection and 67 handler's release are executed unchanged.
    close.write32(close.command+0x10,1);sent=len(close.trade_packets)
    close.invoke(0x4f6ce0,(p,2,0,0,1,1),this=close.command)
    assert len(close.trade_packets)==sent
    close.receive(0x52b86b,transaction_reply(1,4100,request_id=close_request['request_id']))
    assert close.read32(close.command+0x10)==0
    close.invoke(0x4f6ce0,(p,2,0,0,1,1),this=close.command)
    assert parse_item_use_request(close.trade_packets[-1])['sequence']==2 and not close.assertions
    return {'passed':True,'native_request':request,'native_request_hex':built.hex(),
        'native_vitals':actual,'native_quantity_after_use':1,'native_pending_command_released':True,
        'native_shop_close_request':close_request,'native_shop_close_ack_releases_use':True,
        'assertions':f.assertions,'substitutions':['OS clock','Initialized world-ready gate','Native transport enqueue capture',
            'Inherited inventory fixture C++ strings, collection, resource manager and Windows graphical refresh boundaries'],
        'limitations':['Does not establish mouse operation, cast animation or combat interruption']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True)
    a=p.parse_args();result=run(a.binary)
    Path(a.out).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('ORIGINAL_ITEM_USE_BUILDER_VITALS_AND_QUANTITY_PASS')
