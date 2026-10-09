"""Persistent local characters; resource-dependent world fields remain unknown.

Only fields shared by the original creation preview and selection model loader
are mapped. Raw creation parameters are retained so later recovery is lossless.
"""
import json
import sqlite3
import struct
from character_packets import character_record
from character_mutation_packets import parse_create_request


class CharacterRejected(ValueError):
    pass


def native_character_fields(character_id,name,parameters):
    raw=name.encode('utf-16le')
    if not raw or len(raw)>62 or '\0' in name:
        raise CharacterRejected('Name cannot fit original selector')
    if parameters[0] not in range(1,6) or parameters[1] not in (1,2):
        raise CharacterRejected('Original selector preserves preview models for class 1..5, variant 1..2')
    # Original 51f930 defaults profile+4c to 1; shared 4d81f0/518ed0 arguments.
    # 5afa30 (creation preview) <-> 434bc0/5af240 (selection model).
    if any(v>127 for v in (parameters[2],parameters[3],parameters[6])):
        raise CharacterRejected('Appearance does not fit recovered signed byte fields')
    b=bytearray(248)
    struct.pack_into('<III',b,0x14,13,*character_id)  # original constructor kind, local IDs
    struct.pack_into('<II',b,0x30,1,parameters[1])
    struct.pack_into('<I',b,0x44,parameters[0])
    b[0x3c],b[0x3d],b[0x40]=parameters[2],parameters[3],parameters[6]
    b[0x48:0x48+len(raw)]=raw
    return bytes(b)


class CharacterStore:
    def __init__(self,accounts):
        self.accounts=accounts
        with accounts.lock:
            accounts.db.execute('''CREATE TABLE IF NOT EXISTS characters(
                id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL,
                name TEXT NOT NULL UNIQUE, parameters TEXT NOT NULL, native_fields BLOB NOT NULL,
                creation_packet BLOB NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP)''')
            accounts.db.commit()

    def create(self,account_id,packet):
        parsed=parse_create_request(packet)
        name,parameters=parsed['name'],parsed['parameters']
        # Validate before allocating a persistent ID; unknown data is preserved below.
        native_character_fields((0,account_id),name,parameters)
        with self.accounts.lock:
            db=self.accounts.db
            if db.execute('SELECT COUNT(*) FROM characters WHERE account_id=?',(account_id,)).fetchone()[0]>=3:
                raise CharacterRejected('All three original character slots are occupied')
            try:
                with db:
                    cursor=db.execute('INSERT INTO characters(account_id,name,parameters,native_fields,creation_packet) VALUES(?,?,?,?,?)',
                                      (account_id,name,json.dumps(parameters),b'',packet))
                    identity=(cursor.lastrowid,account_id)
                    if identity[0]>0xffffffff:raise CharacterRejected('Local character ID space exhausted')
                    db.execute('UPDATE characters SET native_fields=? WHERE id=?',
                               (native_character_fields(identity,name,parameters),identity[0]))
            except sqlite3.IntegrityError as exc:
                raise CharacterRejected('Character name already exists') from exc
        return identity

    def list(self,account_id):
        with self.accounts.lock:
            rows=self.accounts.db.execute('SELECT id,name,native_fields FROM characters WHERE account_id=? ORDER BY id',
                                          (account_id,)).fetchall()
        return [{'identity':(row[0],account_id),'name':row[1],'native_fields':bytes(row[2]),
                 'record':character_record(bytes(row[2]),row[1])} for row in rows]

    def delete(self,account_id,identity):
        if identity[1]!=account_id:raise CharacterRejected('Character does not belong to this account')
        with self.accounts.lock:
            with self.accounts.db:
                cursor=self.accounts.db.execute('DELETE FROM characters WHERE id=? AND account_id=?',(identity[0],account_id))
                if cursor.rowcount!=1:raise CharacterRejected('Character is missing or belongs to another account')
                # Older stores may predate position migration; no table is required
                # by standalone character-list tools.
                for table in ('world_positions','world_profile_positions','world_wallets','world_inventory_items','world_trade_ledger'):
                    if self.accounts.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
                        self.accounts.db.execute(f'DELETE FROM {table} WHERE character_id=? AND account_id=?',(identity[0],account_id))
