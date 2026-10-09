"""Atomic local wallet, item instances and transaction replay protection."""
import hashlib
import json
from world_inventory_packets import (LOCAL_INITIAL_MONEY,LOCAL_STACK_LIMIT,
    LOCAL_BAG_CAPACITY,MAX_NATIVE_MONEY)


class TradeRejected(ValueError):pass


class WorldInventoryStore:
    def __init__(self,accounts):
        self.accounts=accounts
        with accounts.lock,accounts.db:
            accounts.db.execute('''CREATE TABLE IF NOT EXISTS world_wallets(
                character_id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL,
                money INTEGER NOT NULL CHECK(money BETWEEN 0 AND 10000000))''')
            accounts.db.execute('''CREATE TABLE IF NOT EXISTS world_inventory_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL, source_key TEXT NOT NULL,
                catalog_index INTEGER NOT NULL, name TEXT NOT NULL,
                buy_price INTEGER NOT NULL, sell_price INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 20),
                UNIQUE(character_id,account_id,source_key,catalog_index))''')
            accounts.db.execute('''CREATE TABLE IF NOT EXISTS world_trade_ledger(
                id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL, connection_key TEXT NOT NULL,
                sequence INTEGER NOT NULL, request_hash TEXT NOT NULL,
                opcode INTEGER NOT NULL, snapshot TEXT NOT NULL,
                created TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(connection_key,sequence))''')
            accounts.db.execute('''CREATE TABLE IF NOT EXISTS world_vitals(
                character_id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL,
                hp INTEGER NOT NULL, tp INTEGER NOT NULL,
                max_hp INTEGER NOT NULL CHECK(max_hp>0), max_tp INTEGER NOT NULL CHECK(max_tp>=0),
                CHECK(hp BETWEEN 0 AND max_hp), CHECK(tp BETWEEN 0 AND max_tp))''')

    def _ensure(self,account_id,identity):
        db=self.accounts.db
        if identity[1]!=account_id or db.execute('SELECT 1 FROM characters WHERE id=? AND account_id=?',identity).fetchone() is None:
            raise TradeRejected('Character not owned or missing')
        db.execute('INSERT OR IGNORE INTO world_wallets VALUES(?,?,?)',(*identity,LOCAL_INITIAL_MONEY))
        # Provisional offline level-one limits; no official stat table recovered.
        db.execute('INSERT OR IGNORE INTO world_vitals VALUES(?,?,100,30,100,30)',identity)

    def _vitals(self,identity):
        row=self.accounts.db.execute('SELECT hp,tp,max_hp,max_tp FROM world_vitals WHERE character_id=? AND account_id=?',identity).fetchone()
        return dict(zip(('hp','tp','max_hp','max_tp'),row))

    def load_vitals(self,account_id,identity):
        with self.accounts.lock,self.accounts.db:
            self._ensure(account_id,identity)
            return self._vitals(identity)

    def use(self,account_id,identity,request,payload,connection_key):
        from world_item_definitions import RECOVERY
        if request['identity']!=identity or request['target'] not in ((0,0),identity) or request['opcode']!=0x55 or request['location']!=2 or request['count'] not in (0,1) or request['slot'] < -1:
            raise TradeRejected('Item recovery currently supports the owning character only')
        digest=hashlib.sha256(payload).hexdigest()
        with self.accounts.lock,self.accounts.db:
            self._ensure(account_id,identity);db=self.accounts.db
            prior=db.execute('SELECT character_id,account_id,request_hash FROM world_trade_ledger WHERE connection_key=? AND sequence=?',
                (connection_key,request['sequence'])).fetchone()
            if prior:
                if prior!=(identity[0],account_id,digest):raise TradeRejected('Conflicting native command sequence')
                return self._snapshot(identity),self._vitals(identity),True
            before=self._snapshot(identity);vitals=self._vitals(identity)
            item=next((x for x in before['items'] if tuple(x['identity'])==request['item']),None)
            if item is None:raise TradeRejected('Missing or foreign item instance')
            if request['slot']>=0 and (request['slot']>=len(before['items']) or before['items'][request['slot']]['identity']!=item['identity']):
                raise TradeRejected('Inventory slot does not match item instance')
            effect=RECOVERY.get(item['name'])
            if effect is None:raise TradeRejected('This item effect has not been implemented')
            if vitals['hp']==0:raise TradeRejected('Recovery gummy cannot revive a defeated character')
            hp=min(vitals['max_hp'],vitals['hp']+effect[0]);tp=min(vitals['max_tp'],vitals['tp']+effect[1])
            if (hp,tp)==(vitals['hp'],vitals['tp']):raise TradeRejected('HP and TP do not need this recovery item')
            item_id=item['identity'][0]-0x71000000
            if item['quantity']==1:db.execute('DELETE FROM world_inventory_items WHERE id=? AND character_id=? AND account_id=?',(item_id,*identity))
            else:db.execute('UPDATE world_inventory_items SET quantity=quantity-1 WHERE id=? AND character_id=? AND account_id=?',(item_id,*identity))
            db.execute('UPDATE world_vitals SET hp=?,tp=? WHERE character_id=? AND account_id=?',(hp,tp,*identity))
            snapshot=self._snapshot(identity);vitals=self._vitals(identity)
            db.execute('''INSERT INTO world_trade_ledger(character_id,account_id,connection_key,sequence,request_hash,opcode,snapshot)
                VALUES(?,?,?,?,?,?,?)''',(*identity,connection_key,request['sequence'],digest,0x55,json.dumps(snapshot,ensure_ascii=False)))
            return snapshot,vitals,False

    def _snapshot(self,identity):
        db=self.accounts.db
        money=db.execute('SELECT money FROM world_wallets WHERE character_id=? AND account_id=?',identity).fetchone()[0]
        rows=db.execute('''SELECT id,source_key,catalog_index,name,buy_price,sell_price,quantity
            FROM world_inventory_items WHERE character_id=? AND account_id=? ORDER BY id''',identity).fetchall()
        return {'money':money,'capacity':LOCAL_BAG_CAPACITY,'items':[
            {'identity':(0x71000000+r[0],identity[0],identity[1],0),
             'source_key':r[1],'catalog_index':r[2],'name':r[3],
             'buy_price':r[4],'sell_price':r[5],'quantity':r[6]} for r in rows]}

    def load(self,account_id,identity):
        with self.accounts.lock,self.accounts.db:
            self._ensure(account_id,identity)
            return self._snapshot(identity)

    def trade(self,account_id,identity,source,request,payload,connection_key):
        if request['identity']!=identity or request['opcode'] not in (0xde,0xdf) or not 1<=len(request['lines'])<=4 or any(not isinstance(x['quantity'],int) or not 1<=x['quantity']<=LOCAL_STACK_LIMIT for x in request['lines']):
            raise TradeRejected('Invalid local transaction')
        digest=hashlib.sha256(payload).hexdigest()
        with self.accounts.lock,self.accounts.db:
            self._ensure(account_id,identity)
            db=self.accounts.db
            prior=db.execute('''SELECT character_id,account_id,request_hash,snapshot FROM world_trade_ledger
                WHERE connection_key=? AND sequence=?''',(connection_key,request['sequence'])).fetchone()
            if prior:
                if prior[:3]!=(identity[0],account_id,digest):raise TradeRejected('Conflicting trade sequence')
                return json.loads(prior[3]),True
            before=self._snapshot(identity);money=before['money'];items=before['items']
            if request['opcode']==0xde:
                indices=[line['catalog_index'] for line in request['lines']]
                if len(indices)!=len(set(indices)):raise TradeRejected('Duplicate catalog line')
                for line in request['lines']:
                    index,quantity=line['catalog_index'],line['quantity']
                    if not 0<=index<len(source['stock']):raise TradeRejected('Unknown catalog index')
                    item=source['stock'][index]
                    old=next((x for x in items if x['source_key']==source['key'] and x['catalog_index']==index),None)
                    if (old['quantity'] if old else 0)+quantity>LOCAL_STACK_LIMIT:raise TradeRejected('Local stack full')
                    if old is None and len(items)>=LOCAL_BAG_CAPACITY:raise TradeRejected('Local bag full')
                    cost=item['price_gald']*quantity
                    if cost>money:raise TradeRejected('Insufficient funds')
                    money-=cost
                    db.execute('''INSERT INTO world_inventory_items(character_id,account_id,source_key,catalog_index,name,buy_price,sell_price,quantity)
                        VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(character_id,account_id,source_key,catalog_index)
                        DO UPDATE SET quantity=quantity+excluded.quantity''',
                        (*identity,source['key'],index,item['name'],item['price_gald'],item['price_gald']//2,quantity))
                    # Count distinct new stacks as the batch proceeds.
                    items=self._snapshot(identity)['items']
            else:
                identities=[tuple(line['identity']) for line in request['lines']]
                if len(identities)!=len(set(identities)):raise TradeRejected('Duplicate item instance')
                for line in request['lines']:
                    item=next((x for x in items if x['identity']==tuple(line['identity'])),None)
                    quantity=line['quantity']
                    if item is None or quantity>item['quantity']:raise TradeRejected('Missing item or insufficient quantity')
                    money+=item['sell_price']*quantity
                    if money>MAX_NATIVE_MONEY:raise TradeRejected('Native wallet full')
                    item_id=item['identity'][0]-0x71000000
                    if quantity==item['quantity']:
                        db.execute('DELETE FROM world_inventory_items WHERE id=? AND character_id=? AND account_id=?',(item_id,*identity))
                    else:
                        db.execute('UPDATE world_inventory_items SET quantity=quantity-? WHERE id=? AND character_id=? AND account_id=?',(quantity,item_id,*identity))
            db.execute('UPDATE world_wallets SET money=? WHERE character_id=? AND account_id=?',(money,*identity))
            result=self._snapshot(identity)
            db.execute('''INSERT INTO world_trade_ledger(character_id,account_id,connection_key,sequence,request_hash,opcode,snapshot)
                VALUES(?,?,?,?,?,?,?)''',(*identity,connection_key,request['sequence'],digest,request['opcode'],json.dumps(result,ensure_ascii=False)))
            return result,False
