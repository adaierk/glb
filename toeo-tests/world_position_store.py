"""Durable locally accepted destinations, isolated per original character.

The native client animates its accepted path locally. A saved position is the
accepted destination, so closing during an animation resumes at that endpoint.
"""
from world_map_packets import LOCAL_MAP_ID
from world_map_navigation import NAV_RLE,NAV_WIDTH,GRID_WIDTH,GRID_HEIGHT

_slots=bytearray()
for value,count in zip(NAV_RLE[::2],NAV_RLE[1::2]):_slots.extend(bytes((value,))*count)

def walkable_grid(grid):
    x,y=grid
    return (isinstance(x,int) and isinstance(y,int) and 0<=x<GRID_WIDTH and 0<=y<GRID_HEIGHT
            and (x-y)%2==0 and bool(_slots[y*NAV_WIDTH+x//2]))

class WorldPositionStore:
    def __init__(self,accounts,profile=None):
        self.accounts=accounts
        from world_profiles import world_profile
        self.profile=world_profile(profile or 'forest')
        self.table='world_positions' if self.profile.map_id==LOCAL_MAP_ID else 'world_profile_positions'
        with accounts.lock:
            accounts.db.execute('''CREATE TABLE IF NOT EXISTS world_positions(
                character_id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL,
                map_id INTEGER NOT NULL, grid_x INTEGER NOT NULL, grid_y INTEGER NOT NULL,
                updated TEXT DEFAULT CURRENT_TIMESTAMP)''')
            accounts.db.commit()
            accounts.db.execute('''CREATE TABLE IF NOT EXISTS world_profile_positions(
                character_id INTEGER NOT NULL, account_id INTEGER NOT NULL,
                map_id INTEGER NOT NULL, grid_x INTEGER NOT NULL, grid_y INTEGER NOT NULL,
                updated TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(character_id,account_id,map_id))''')
            accounts.db.commit()

    def load(self,account_id,identity):
        if identity[1]!=account_id:raise ValueError('Character account mismatch')
        with self.accounts.lock:
            role=self.accounts.db.execute('SELECT 1 FROM characters WHERE id=? AND account_id=?',identity).fetchone()
            if role is None:raise ValueError('Character not owned or missing')
            row=self.accounts.db.execute(f'SELECT map_id,grid_x,grid_y FROM {self.table} WHERE character_id=? AND account_id=? AND map_id=?',(*identity,self.profile.map_id)).fetchone()
        if row and self.profile.walkable(row[1:]):
            return {'map_id':row[0],'grid':tuple(row[1:]),'restored':True}
        return {'map_id':self.profile.map_id,'grid':self.profile.spawn_grid,'restored':False}

    def save(self,account_id,identity,map_id,grid):
        if identity[1]!=account_id or map_id!=self.profile.map_id or not self.profile.walkable(grid):
            raise ValueError('Invalid character, map or walkable destination')
        with self.accounts.lock:
            db=self.accounts.db
            if db.execute('SELECT 1 FROM characters WHERE id=? AND account_id=?',identity).fetchone() is None:
                raise ValueError('Character not owned or missing')
            with db:
                conflict='character_id' if self.table=='world_positions' else 'character_id,account_id,map_id'
                db.execute(f'''INSERT INTO {self.table}(character_id,account_id,map_id,grid_x,grid_y)
                    VALUES(?,?,?,?,?) ON CONFLICT({conflict}) DO UPDATE SET
                    account_id=excluded.account_id,map_id=excluded.map_id,grid_x=excluded.grid_x,
                    grid_y=excluded.grid_y,updated=CURRENT_TIMESTAMP''',(*identity,map_id,*grid))
