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
            columns={r[1] for r in accounts.db.execute('PRAGMA table_info(world_inventory_items)')}
            if 'slot' not in columns:
                accounts.db.execute('ALTER TABLE world_inventory_items ADD COLUMN slot INTEGER')
            for char,account in accounts.db.execute('SELECT DISTINCT character_id,account_id FROM world_inventory_items'):
                used={r[0] for r in accounts.db.execute('SELECT slot FROM world_inventory_items WHERE character_id=? AND account_id=? AND slot IS NOT NULL',(char,account))}
                missing=accounts.db.execute('SELECT id FROM world_inventory_items WHERE character_id=? AND account_id=? AND slot IS NULL ORDER BY id',(char,account)).fetchall()
                for (item_id,) in missing:
                    slot=next((x for x in range(LOCAL_BAG_CAPACITY) if x not in used),None)
                    if slot is None:raise TradeRejected('Legacy inventory exceeds local bag capacity')
                    accounts.db.execute('UPDATE world_inventory_items SET slot=? WHERE id=?',(slot,item_id));used.add(slot)
            if 'location' not in columns:accounts.db.execute('ALTER TABLE world_inventory_items ADD COLUMN location INTEGER NOT NULL DEFAULT 2')
            if 'definition_key' not in columns:accounts.db.execute('ALTER TABLE world_inventory_items ADD COLUMN definition_key TEXT')
            accounts.db.execute('DROP INDEX IF EXISTS world_inventory_unique_slot')
            accounts.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS world_inventory_unique_location_slot ON world_inventory_items(character_id,account_id,location,slot)')
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
            if request['slot']>=0 and request['slot']!=item['slot']:
                raise TradeRejected('Inventory slot does not match item instance')
            effect=RECOVERY.get(item['name'])
            if effect is None:raise TradeRejected('This item effect has not been implemented')
            if vitals['hp']==0:raise TradeRejected('Recovery gummy cannot revive a defeated character')
            hp=min(vitals['max_hp'],vitals['hp']+effect[0]);tp=min(vitals['max_tp'],vitals['tp']+effect[1])
            if (hp,tp)==(vitals['hp'],vitals['tp']):raise TradeRejected('HP and TP do not need this recovery item')
            item_id=item['identity'][0]-0x71000000
            if item['quantity']==1:
                db.execute('DELETE FROM world_inventory_items WHERE id=? AND character_id=? AND account_id=?',(item_id,*identity))
                self._reindex(identity)
            else:db.execute('UPDATE world_inventory_items SET quantity=quantity-1 WHERE id=? AND character_id=? AND account_id=?',(item_id,*identity))
            db.execute('UPDATE world_vitals SET hp=?,tp=? WHERE character_id=? AND account_id=?',(hp,tp,*identity))
            snapshot=self._snapshot(identity);vitals=self._vitals(identity)
            db.execute('''INSERT INTO world_trade_ledger(character_id,account_id,connection_key,sequence,request_hash,opcode,snapshot)
                VALUES(?,?,?,?,?,?,?)''',(*identity,connection_key,request['sequence'],digest,0x55,json.dumps(snapshot,ensure_ascii=False)))
            return snapshot,vitals,False

    def _snapshot(self,identity):
        db=self.accounts.db
        money=db.execute('SELECT money FROM world_wallets WHERE character_id=? AND account_id=?',identity).fetchone()[0]
        rows=db.execute('''SELECT id,source_key,catalog_index,name,buy_price,sell_price,quantity,slot,location,definition_key
            FROM world_inventory_items WHERE character_id=? AND account_id=? ORDER BY location,slot''',identity).fetchall()
        items=[
            {'identity':(0x71000000+r[0],identity[0],identity[1],0),
             'source_key':r[1],'catalog_index':r[2],'name':r[3],
             'buy_price':r[4],'sell_price':r[5],'quantity':r[6],'slot':r[7],'location':r[8],'definition_key':r[9]} for r in rows]
        return {'money':money,'capacity':LOCAL_BAG_CAPACITY,'items':[x for x in items if x['location']==2],'equipment':[x for x in items if x['location']==4]}

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
                    slot=old['slot'] if old else next(x for x in range(LOCAL_BAG_CAPACITY) if x not in {v['slot'] for v in items})
                    db.execute('''INSERT INTO world_inventory_items(character_id,account_id,source_key,catalog_index,name,buy_price,sell_price,quantity,slot)
                        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(character_id,account_id,source_key,catalog_index)
                        DO UPDATE SET quantity=quantity+excluded.quantity''',
                        (*identity,source['key'],index,item['name'],item['price_gald'],item['price_gald']//2,quantity,slot))
                    # Count distinct new stacks as the batch proceeds.
                    items=self._snapshot(identity)['items']
            else:
                identities=[tuple(line['identity']) for line in request['lines']]
                if len(identities)!=len(set(identities)):raise TradeRejected('Duplicate item instance')
                for line in request['lines']:
                    item=next((x for x in items if x['identity']==tuple(line['identity'])),None)
                    quantity=line['quantity']
                    if item is not None and item.get('definition_key'):raise TradeRejected('Equipment fixture is not sold through historical merchants')
                    if item is None or quantity>item['quantity']:raise TradeRejected('Missing item or insufficient quantity')
                    money+=item['sell_price']*quantity
                    if money>MAX_NATIVE_MONEY:raise TradeRejected('Native wallet full')
                    item_id=item['identity'][0]-0x71000000
                    if quantity==item['quantity']:
                        db.execute('DELETE FROM world_inventory_items WHERE id=? AND character_id=? AND account_id=?',(item_id,*identity))
                        self._reindex(identity)
                    else:
                        db.execute('UPDATE world_inventory_items SET quantity=quantity-? WHERE id=? AND character_id=? AND account_id=?',(quantity,item_id,*identity))
            db.execute('UPDATE world_wallets SET money=? WHERE character_id=? AND account_id=?',(money,*identity))
            result=self._snapshot(identity)
            db.execute('''INSERT INTO world_trade_ledger(character_id,account_id,connection_key,sequence,request_hash,opcode,snapshot)
                VALUES(?,?,?,?,?,?,?)''',(*identity,connection_key,request['sequence'],digest,request['opcode'],json.dumps(result,ensure_ascii=False)))
            return result,False


    def move(self,account_id,identity,request,payload,connection_key):
        if request['source_location']==4 or request['destination_location']==4:
            return self._move_equipment(account_id,identity,request,payload,connection_key)
        if request['identity']!=identity or request['opcode']!=0x54 or request['source_location']!=2 or request['destination_location']!=2 or request['count']!=-1 or request['context']!=0 or not 0<=request['source_slot']<LOCAL_BAG_CAPACITY or not -1<=request['destination_slot']<LOCAL_BAG_CAPACITY:
            raise TradeRejected('Only complete-stack bag moves are supported')
        digest=hashlib.sha256(payload).hexdigest()
        with self.accounts.lock,self.accounts.db:
            self._ensure(account_id,identity);db=self.accounts.db
            prior=db.execute('SELECT character_id,account_id,request_hash FROM world_trade_ledger WHERE connection_key=? AND sequence=?',(connection_key,request['sequence'])).fetchone()
            if prior:
                if prior!=(identity[0],account_id,digest):raise TradeRejected('Conflicting native command sequence')
                return self._snapshot(identity),True
            before=self._snapshot(identity)
            source=next((x for x in before['items'] if x['identity']==request['item']),None)
            destination=next((x for x in before['items'] if x['slot']==request['destination_slot']),None)
            if request['destination_slot']>=len(before['items']):raise TradeRejected('Destination outside native packed bag')
            if source is None or source['slot']!=request['source_slot']:raise TradeRejected('Missing item or stale source slot')
            expected=(0,0,0,0) if destination is None else destination['identity']
            if expected!=request['destination_item']:raise TradeRejected('Destination changed or foreign item')
            ordered=[x['identity'][0]-0x71000000 for x in before['items']]
            source_index=source['slot']
            if destination is not None:
                target_index=destination['slot']
                ordered[source_index],ordered[target_index]=ordered[target_index],ordered[source_index]
            else:ordered.append(ordered.pop(source_index))
            self._reindex(identity,ordered)
            result=self._snapshot(identity)
            db.execute('INSERT INTO world_trade_ledger(character_id,account_id,connection_key,sequence,request_hash,opcode,snapshot) VALUES(?,?,?,?,?,?,?)',(*identity,connection_key,request['sequence'],digest,0x54,json.dumps(result,ensure_ascii=False)))
            return result,False


    def _reindex(self,identity,ordered_ids=None):
        db=self.accounts.db
        ordered_ids=ordered_ids if ordered_ids is not None else [r[0] for r in db.execute('SELECT id FROM world_inventory_items WHERE character_id=? AND account_id=? AND location=2 ORDER BY slot',identity)]
        for item_id in ordered_ids:db.execute('UPDATE world_inventory_items SET slot=? WHERE id=? AND character_id=? AND account_id=?',(-item_id,item_id,*identity))
        for slot,item_id in enumerate(ordered_ids):db.execute('UPDATE world_inventory_items SET slot=? WHERE id=? AND character_id=? AND account_id=?',(slot,item_id,*identity))

    def grant_equipment_preview(self,account_id,identity):
        """Opt-in local fixture grant. Does not alter shop stock or official IDs."""
        from world_equipment_definitions import DEFINITIONS,EQUIPMENT_SOURCE
        with self.accounts.lock,self.accounts.db:
            self._ensure(account_id,identity);db=self.accounts.db
            for index,(key,value) in enumerate(DEFINITIONS.items()):
                if db.execute('SELECT 1 FROM world_inventory_items WHERE character_id=? AND account_id=? AND definition_key=?',(*identity,key)).fetchone():continue
                bag=self._snapshot(identity)['items']
                if len(bag)>=LOCAL_BAG_CAPACITY:raise TradeRejected('Local bag full')
                db.execute('INSERT INTO world_inventory_items(character_id,account_id,source_key,catalog_index,name,buy_price,sell_price,quantity,slot,location,definition_key) VALUES(?,?,?,?,?,0,0,1,?,2,?)',(*identity,EQUIPMENT_SOURCE,index,value['name'],len(bag),key))
            return self._snapshot(identity)

    def _move_equipment(self,account_id,identity,request,payload,connection_key):
        from world_equipment_definitions import equipment_definition
        if request['identity']!=identity or request['opcode']!=0x54 or request['source_location'] not in (2,4) or request['destination_location'] not in (2,4) or request['source_location']==request['destination_location'] or request['count']!=-1 or request['context']!=0:
            raise TradeRejected('Unsupported equipment move')
        digest=hashlib.sha256(payload).hexdigest()
        with self.accounts.lock,self.accounts.db:
            self._ensure(account_id,identity);db=self.accounts.db
            prior=db.execute('SELECT character_id,account_id,request_hash FROM world_trade_ledger WHERE connection_key=? AND sequence=?',(connection_key,request['sequence'])).fetchone()
            if prior:
                if prior!=(identity[0],account_id,digest):raise TradeRejected('Conflicting native command sequence')
                return self._snapshot(identity),True
            before=self._snapshot(identity);all_items=before['items']+before['equipment']
            source=next((x for x in all_items if x['identity']==request['item']),None)
            if source is None or source['location']!=request['source_location'] or (request['source_slot']!=-1 and source['slot']!=request['source_slot']):raise TradeRejected('Missing equipment or stale source slot')
            definition=equipment_definition(source)
            if definition is None or source['quantity']!=1:raise TradeRejected('Item is not supported equipment')
            target_location=request['destination_location'];slot=request['destination_slot']
            if target_location==4:
                if slot!=definition['slot']:raise TradeRejected('Equipment body slot does not match')
            elif not -1<=slot<len(before['items']):raise TradeRejected('Destination outside native packed bag')
            target=next((x for x in all_items if x['location']==target_location and x['slot']==slot),None)
            expected=(0,0,0,0) if target is None else target['identity']
            # Original drag to an occupied equipment cell may send zero target:
            # require explicit identity for replacement until that UI flow is verified.
            if request['destination_item']!=expected:raise TradeRejected('Equipment destination changed')
            if target is not None:raise TradeRejected('Equipment replacement is not verified yet')
            if target_location==2 and len(before['items'])>=LOCAL_BAG_CAPACITY:raise TradeRejected('Local bag full')
            item_id=source['identity'][0]-0x71000000
            db.execute('UPDATE world_inventory_items SET location=?,slot=? WHERE id=? AND character_id=? AND account_id=?',(target_location,slot if target_location==4 else -item_id,item_id,*identity))
            ordered=[x['identity'][0]-0x71000000 for x in before['items'] if x['identity']!=source['identity']]
            if target_location==2:ordered.insert(len(ordered) if slot==-1 else slot,item_id)
            self._reindex(identity,ordered)
            result=self._snapshot(identity)
            bonus=sum(equipment_definition(x)['max_hp_bonus'] for x in result['equipment'])
            maximum=100+bonus
            db.execute('UPDATE world_vitals SET max_hp=?,hp=MIN(hp,?) WHERE character_id=? AND account_id=?',(maximum,maximum,*identity))
            db.execute('INSERT INTO world_trade_ledger(character_id,account_id,connection_key,sequence,request_hash,opcode,snapshot) VALUES(?,?,?,?,?,?,?)',(*identity,connection_key,request['sequence'],digest,0x54,json.dumps(result,ensure_ascii=False)))
            return result,False
