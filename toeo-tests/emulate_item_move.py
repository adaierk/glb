"""Execute unchanged 54 builder and 67/6B bag-order decoder boundaries."""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESP
from emulate_item_use import UseFixture
from world_inventory_packets import parse_item_move_request,inventory_notice,transaction_reply

class MoveFixture(UseFixture):
    def __init__(self,binary):super().__init__(binary);self.inserts=[]
    def on_code(self,uc,va,size,context):
        if va==0x51ea20:
            sp=uc.reg_read(UC_X86_REG_ESP);obj=uc.reg_read(UC_X86_REG_ECX)
            self.inserts.append({'container':obj,'slot':self.read32(sp+4),'item':self.read32(sp+8)})
        super().on_code(uc,va,size,context)

def run(binary):
    f=MoveFixture(binary);p=0x10e3000;instance=(0x71000001,1,1,0)
    f.uc.mem_write(p,struct.pack('<IIII',*instance));f.uc.mem_write(p+32,struct.pack('<IIII',0x71000002,1,1,0))
    f.invoke(0x4f6ba0,(p,2,0,0xffffffff,2,1,p+32,0),this=f.command)
    request=parse_item_move_request(f.trade_packets[-1]);assert request['source_slot']==0 and request['destination_slot']==1 and request['count']==-1
    snapshot={'money':4100,'capacity':32,'items':[{'identity':(0x71000002,1,1,0),'catalog_index':1,'slot':0,'quantity':1,'name':'ミックスグミ','buy_price':360,'sell_price':180},{'identity':instance,'catalog_index':0,'slot':1,'quantity':1,'name':'レモングミ','buy_price':360,'sell_price':180}]}
    f.receive(0x52b8ef,inventory_notice((1,1),request['map_id'],snapshot))
    assert f.inserts[-1]['slot']==0xffffffff
    f.write32(f.command+0x10,1);f.receive(0x52b86b,transaction_reply(1,4100,request_id=request['request_id'],snapshot=snapshot))
    assert f.inserts[-1]['slot']==1 and f.read32(f.command+0x10)==0
    item=next(x for x in f.collections[f.inventory] if bytes(f.uc.mem_read(x,16))==struct.pack('<IIII',*instance));assert struct.unpack('<h',f.uc.mem_read(item+0x24,2))[0]==1 and f.read32(item+0x30)==3811 and not f.assertions
    return {'passed':True,'original_request':request,'request_hex':f.trade_packets[-1].hex(),'native_receipt_insert_slot':1,'native_notice_uses_packed_order':True,'native_quantity':1,'pending_released':True,'assertions':f.assertions,'substitutions':['Inherited item-use fixture OS/transport/C++ strings/container and UI lifetime boundaries'],'limitations':['Does not establish Windows drag/drop; equipment, stack splitting and merging remain separate']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    Path(a.out).write_text(json.dumps(run(a.binary),indent=2));print('ORIGINAL_ITEM_MOVE_BUILDER_AND_BAG_ORDER_REPLY_PASS')
