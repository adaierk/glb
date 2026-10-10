"""Explicit offline equipment fixtures, not recovered official item masters.
Original slot names are from the unmodified client's 7A6D50 command table.
Test items are opt-in and are never inserted into the historical merchant.
"""
EQUIPMENT_SOURCE='offline-equipment-fixture-v17'
DEFINITIONS={
 'test-sword':{'name':'Local Test Sword','catalog_id':0x7001,'slot':1,'icon_type':1,'icon_offset':0,'max_hp_bonus':0},
 'test-body':{'name':'Local Test Body','catalog_id':0x7002,'slot':2,'icon_type':2,'icon_offset':0,'max_hp_bonus':10},
}
SLOT_NAMES={1:'weapon',2:'body',3:'head',4:'arm',15:'shield',5:'ring',6:'neck',7:'hands',8:'legs',9:'accessory',10:'back',11:'u.head',12:'u.body',13:'1.growth',14:'2.growth'}
def equipment_definition(item):
 key=item.get('definition_key')
 if key is None:return None
 try:return DEFINITIONS[key]
 except KeyError:raise ValueError('Unknown local equipment definition') from None
