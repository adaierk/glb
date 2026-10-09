"""Execute unchanged original DE/DF builders and 36..3D item decoder.

CRT strings, container lookups/insertion, resource lookup and transport are
declared boundaries. Original quantities, identity fields, NAME: parsing and
checksum-protected money read/write execute original x86 instructions.
"""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EIP
from emulate_shop_catalog import CatalogFixture
from world_inventory_packets import inventory_records,parse_trade_request,inventory_notice,transaction_reply
from world_npc_packets import SHOP_IDENTITY


class InventoryFixture(CatalogFixture):
    def __init__(self,binary):
        self.collections={};self.trade_packets=[];self.wide_arena=0x1300000
        super().__init__(binary)
        self.buffer=0x10e0000;self.wallet=0x10e1000;self.inventory=0x10e2000
        self.command=0x10e5000;self.write32(self.game+0x90,self.command)
        self.write32(self.netstate+0x28,self.buffer);self.write32(self.netstate+0x2c,self.buffer+4096)
        self.write32(self.player+0x1d4,self.wallet);self.write32(self.player+0x1d8,self.inventory)
        for i,iat in enumerate((0x6e2338,0x6e2530,0x6e2534,0x6e2520)):
            self.write32(iat,0x10df000+i*16)

    def wide(self,p):
        result=bytearray()
        for i in range(2048):
            word=bytes(self.uc.mem_read(p+2*i,2))
            if word==b'\0\0':return result.decode('utf-16le')
            result.extend(word)
        raise ValueError('Unterminated fixture string')

    def on_code(self,uc,va,size,context):
        sp=uc.reg_read(UC_X86_REG_ESP);obj=uc.reg_read(UC_X86_REG_ECX)
        if va==0x10df000:
            value=self.item_strings.get(obj,'').encode('utf-16le')+b'\0\0'
            p=self.wide_arena;self.wide_arena+=len(value)+16;uc.mem_write(p,value);self.ret(p)
        elif va==0x10df010:
            p,q=self.read32(sp+4),self.read32(sp+8)
            index=self.wide(p).find(self.wide(q));self.ret(0 if index<0 else p+index*2)
        elif va==0x10df020:
            p,q,count=(self.read32(sp+i) for i in (4,8,12))
            uc.mem_write(p,bytes(uc.mem_read(q,count*2)));self.ret(p)
        elif va==0x10df030:
            p,character=self.read32(sp+4),self.read32(sp+8)
            index=self.wide(p).find(chr(character));self.ret(0 if index<0 else p+index*2)
        elif va==0x51ef30:
            self.collections[obj]=[];uc.mem_write(obj,bytes(16));self.ret()
        elif va==0x51ea20 and obj!=self.shop+0x114:
            item=self.read32(sp+8);values=self.collections.setdefault(obj,[])
            values.append(item);self.write32(obj+8,len(values));self.ret(len(values)-1,8)
        elif va==0x51db30:
            identity=bytes(uc.mem_read(self.read32(sp+4),16))
            item=next((p for p in self.collections.get(obj,[]) if bytes(uc.mem_read(p,16))==identity),0)
            self.ret(item,4)
        elif va==0x4260d0:self.ret(self.buffer)
        elif va==0x43d0b0:
            p=self.read32(sp+12);length=struct.unpack('<H',uc.mem_read(p+3,2))[0]
            self.trade_packets.append(bytes(uc.mem_read(p,length)));self.ret(1,20)
        else:super().on_code(uc,va,size,context)


class WorldFixture(InventoryFixture):
    def __init__(self,binary):
        super().__init__(binary)
        self.write32(self.player+0x80,1);self.write32(self.player+0x1dc,0x10e6000)
        self.write32(0x10da008,0x10e7000) # startup transport pending-query registry

    def on_code(self,uc,va,size,context):
        sp=uc.reg_read(UC_X86_REG_ESP);obj=uc.reg_read(UC_X86_REG_ECX)
        if va in (0x4fed50,0x4fedd0,0x4fee60):self.ret() # already initialized actor components
        elif va in (0x51ef90,0x51edf0):
            other=self.read32(sp+4)
            if va==0x51ef90:
                self.collections[obj]=self.collections[other][:]
                self.write32(obj+8,len(self.collections[obj]));self.write32(obj+12,self.read32(other+12))
            self.ret(obj,4) # collection move; decoded items are untouched
        elif va in (0x51f860,0x51efc0,0x4b0080):self.ret() # temporary collection lifetime
        elif va==0x5ba530:self.ret(0,8) # Windows graphical refresh only
        elif va==0x5b52d0:self.ret(0) # graphical inventory absent in this fixture
        elif va==0x609c50:
            p=self.read32(sp+4);self.write32(p,0);self.write32(p+8,0);self.ret(1,4) # pending queue lifetime
        else:super().on_code(uc,va,size,context)


def run(binary):
    f=InventoryFixture(binary);lines=0x10e3000
    f.uc.mem_write(lines,struct.pack('<II',0,3))
    f.invoke(0x4f8050,(*SHOP_IDENTITY,1,lines),this=f.command)
    buy=parse_trade_request(f.trade_packets[-1])
    assert buy['sequence']==1 and buy['lines']==[{'catalog_index':0,'quantity':3}]
    instance=(0x71000001,1,1,0)
    f.uc.mem_write(lines,struct.pack('<IIIIII',*instance,2,1))
    f.invoke(0x4f81b0,(*SHOP_IDENTITY,1,lines),this=f.command)
    sell=parse_trade_request(f.trade_packets[-1])
    assert sell['sequence']==2 and sell['lines']==[{'identity':instance,'quantity':1}]
    snapshot={'money':4100,'capacity':32,'items':[{'identity':instance,'catalog_index':0,
        'quantity':2,'name':'レモングミ','buy_price':360,'sell_price':180}]}
    payload=inventory_records(snapshot)+bytes(4);f.uc.mem_write(f.buffer,payload)
    next_pointer=0x10e4000
    try:f.invoke(0x51f030,(f.buffer,f.inventory,0,0,next_pointer))
    except Exception as e:raise RuntimeError(str(e)+' at '+hex(f.uc.reg_read(UC_X86_REG_EIP))) from e
    assert len(f.collections[f.inventory])==1 and f.read32(f.inventory+12)==32
    item=f.collections[f.inventory][0]
    assert f.item_strings[item+0x34]=='レモングミ'
    assert struct.unpack('<hh',f.uc.mem_read(item+0x24,4))==(2,20)
    assert f.read32(item+0xa4)==360 and f.read32(item+0xa8)==180 and f.read32(item+0x30)==0
    f.invoke(0x51d740,(4100,),this=f.wallet);f.invoke(0x51d8a0,this=f.wallet)
    from unicorn.x86_const import UC_X86_REG_EAX
    assert f.uc.reg_read(UC_X86_REG_EAX)==4100 and not f.assertions
    from world_map_packets import world_initialization_reply
    from character_store import native_character_fields
    initialized=InventoryFixture(binary)
    initialized.invoke(0x4db8f0,this=initialized.data+0x488) # real empty equipment constructor
    p=0x109a000
    initial=world_initialization_reply((1,1),'Archive',native_character_fields((1,1),'Archive',(1,1,0,0,0,0,0,0,0,0)),1,inventory=snapshot)
    initialized.uc.mem_write(p,initial);initialized.invoke(0x43f090,(p,p+40),this=initialized.ui)
    assert initialized.read32(initialized.data+0x470)==4100
    assert initialized.read32(initialized.data+0x478+12)==32
    assert len(initialized.collections[initialized.data+0x478])==1 and not initialized.assertions
    notice=WorldFixture(binary);notice.receive(0x52b8ef,inventory_notice((1,1),0x1120108,snapshot))
    assert notice.read32(notice.wallet)==4100 and len(notice.collections[notice.inventory])==1
    notice.write32(notice.command+0x10,1)
    notice.receive(0x52b86b,transaction_reply(1,3920))
    assert notice.read32(notice.wallet)==3920 and notice.read32(notice.command+4)==1
    assert notice.read32(notice.command+0x10)==0 and not notice.assertions
    return {'passed':True,'native_buy':buy,'native_buy_hex':f.trade_packets[0].hex(),
        'native_sell':sell,'native_sell_hex':f.trade_packets[1].hex(),
        'native_inventory_name':f.item_strings[item+0x34],'native_quantity':2,
        'native_stack_capacity':20,'native_bag_capacity':32,'native_wallet_crc_read':4100,
        'native_world_initial_inventory_restored':True,'native_full_inventory_notice_applied':True,
        'native_transaction_wallet_applied':3920,'native_pending_command_released':True,
        'substitutions':['C++ string and CRT wide string boundaries','Container insertion/lookup/clear',
                         'Resource lookup returns NULL for unresolved template','Network queue and buffer getter',
                         'Initialized actor components, collection moves and temporary lifetimes','Windows graphical refresh','Pending command lifetime'],
        'limitations':['Does not establish native Windows UI buy/sell or official stack/resale rules','Original item templates/icons unresolved']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--out',required=True);a=p.parse_args()
    result=run(a.binary);Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ORIGINAL_TRADE_BUILDERS_INVENTORY_NAME_QUANTITY_WALLET_PASS')
