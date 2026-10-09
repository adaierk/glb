"""Local experimental selection/admission tickets and account-control binding.

Tickets are deliberately connection-bound only once accepted. No ACK is sent
for absent, expired, foreign, or already used tickets; negative world reply
semantics are not recovered yet.
"""
import secrets
import time


class WorldTicketStore:
    def __init__(self,accounts):
        self.accounts=accounts
        with accounts.lock:
            accounts.db.execute('''CREATE TABLE IF NOT EXISTS world_tickets(
                ticket INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, character_id INTEGER NOT NULL,
                expires REAL NOT NULL, claimed_by TEXT)''')
            columns={r[1] for r in accounts.db.execute('PRAGMA table_info(world_tickets)')}
            if 'attached_by' not in columns:accounts.db.execute('ALTER TABLE world_tickets ADD COLUMN attached_by TEXT')
            # A connection identity is process-local. Never revive tickets from an older service run.
            accounts.db.execute('DELETE FROM world_tickets')
            accounts.db.commit()

    def issue(self,account_id,identity,ttl=120):
        if identity[1]!=account_id:raise ValueError('Foreign character ID')
        with self.accounts.lock:
            db=self.accounts.db
            if not db.execute('SELECT 1 FROM characters WHERE id=? AND account_id=?',(identity[0],account_id)).fetchone():
                raise ValueError('Character not found')
            with db:
                db.execute('DELETE FROM world_tickets WHERE expires<=?',(time.time(),))
                for _ in range(128):
                    ticket=secrets.randbelow(65535)+1
                    if not db.execute('SELECT 1 FROM world_tickets WHERE ticket=?',(ticket,)).fetchone():break
                else:raise ValueError('Ticket space busy')
                db.execute('INSERT INTO world_tickets(ticket,account_id,character_id,expires) VALUES(?,?,?,?)',
                           (ticket,account_id,identity[0],time.time()+ttl))
        return ticket

    def claim(self,ticket,connection,account_id=None):
        with self.accounts.lock:
            db=self.accounts.db
            row=db.execute('''SELECT t.account_id,t.character_id,t.expires,t.claimed_by FROM world_tickets t
                JOIN characters c ON c.id=t.character_id AND c.account_id=t.account_id WHERE t.ticket=?''',(ticket,)).fetchone()
            if not row or row[2]<=time.time() or (account_id is not None and row[0]!=account_id):return None
            if row[3] is not None and row[3]!=connection:return None
            with db:db.execute('UPDATE world_tickets SET claimed_by=? WHERE ticket=?',(connection,ticket))
        return {'account_id':row[0],'character_id':(row[1],row[0])}

    def complete(self,account_id,connection):
        """Bind the account-control channel to one unambiguous active admission."""
        with self.accounts.lock:
            db=self.accounts.db
            rows=db.execute('''SELECT t.ticket,t.character_id,t.attached_by FROM world_tickets t
                JOIN characters c ON c.id=t.character_id AND c.account_id=t.account_id
                WHERE t.account_id=? AND t.expires>? AND t.claimed_by IS NOT NULL''',
                (account_id,time.time())).fetchall()
            prior=[r for r in rows if r[2]==connection]
            if len(prior)==1:row=prior[0]
            else:
                pending=[r for r in rows if r[2] is None]
                if len(pending)!=1:return None
                row=pending[0]
            with db:db.execute('UPDATE world_tickets SET attached_by=? WHERE ticket=?',(connection,row[0]))
        return {'ticket':row[0],'account_id':account_id,'character_id':(row[1],account_id)}

    def disconnect(self,connection):
        with self.accounts.lock:
            with self.accounts.db:
                self.accounts.db.execute('DELETE FROM world_tickets WHERE claimed_by=? OR attached_by=?',(connection,connection))
