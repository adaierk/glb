"""Explicit offline equipment fixtures, not recovered official item masters.
Original slot names are from the unmodified client's 7A6D50 command table.
CRSD bank 500 is the untouched pc_weapon.cpd; weapon layer 4 is
selected by the original model setter. Sword has battle sprites only.
Test items are opt-in and are never inserted into the historical merchant.
"""
EQUIPMENT_SOURCE='offline-equipment-fixture-v18'
DEFINITIONS={
 'test-sword':{'name':'Local Test Sword','catalog_id':0x7001,'slot':1,'icon_type':2,'icon_offset':0,'max_hp_bonus':0,'visual_resource':10000,'visual_layer':4,'visual_source_bank':500},
 'test-body':{'name':'Local Test Body','catalog_id':0x7002,'slot':2,'icon_type':3,'icon_offset':0,'max_hp_bonus':10,'visual_resource':4000,'visual_layer':1,'visual_source_bank':0},
}
SLOT_NAMES={1:'weapon',2:'body',3:'head',4:'arm',15:'shield',5:'ring',6:'neck',7:'hands',8:'legs',9:'accessory',10:'back',11:'u.head',12:'u.body',13:'1.growth',14:'2.growth'}
def equipment_definition(item):
 key=item.get('definition_key')
 if key is None:return None
 try:return DEFINITIONS[key]
 except KeyError:raise ValueError('Unknown local equipment definition') from None
