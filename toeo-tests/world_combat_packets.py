"""Recovered original encounter records; spawn/stats are explicit local fixtures."""
import struct
from account_packets import message
from world_map_packets import record
from character_mutation_packets import encode_name
from world_enemy_packets import ENEMY_IDENTITY,ENEMY_NAME,enemy_grid
BATTLE_GROUP=(0x73000001,1)
BATTLE_ENEMY_BANK=1200
BATTLE_ENEMY_RESOURCE_BANK=100
def battle_actor_record(identity,name,appearance,category,position,grid,map_id,hp=100,max_hp=100,tp=0,max_tp=0,controlled=False,battle_model_bank=0,equipment=()):
    if len(appearance)!=24:raise ValueError('Original battle appearance requires 24 bytes')
    b=record(0x59,0x158)
    struct.pack_into('<II',b,4,*identity)
    struct.pack_into('<II',b,0xc,category,0)
    struct.pack_into('<hh',b,0x14,*grid)
    struct.pack_into('<I',b,0x18,map_id)
    struct.pack_into('<II',b,0x24,*BATTLE_GROUP)
    # Original 5299BD copies record+34 into actor direction+8C.
    # Battle ATD assets use horizontal directions 2/6; map directions 0/1 fail animation100.
    struct.pack_into('<iiii',b,0x2c,*position,2 if controlled else 6,1)
    b[0x3c:0x80]=encode_name(name)
    b[0x80:0x98]=appearance
    struct.pack_into('<IIIII',b,0x98,max_hp,hp,max_tp,tp,0)
    # Original529919 copies B4 -> state+8 -> actor+60; model/body and battle routines branch on kind1/2.
    struct.pack_into('<I',b,0xb4,category)
    b[0xc0:0xc5]=bytes((1,1,1,0,1))
    struct.pack_into('<HHH',b,0xc6,1,1,2)
    # Original 529840 -> state+24C -> actor+16C; 5109A0 uses the CRSD bank directly.
    struct.pack_into('<I',b,0xcc,battle_model_bank)
    from world_equipment_definitions import equipment_definition
    components=[]
    for item in equipment:
        definition=equipment_definition(item)
        if definition and definition.get('visual_resource'):components.append((item,definition))
    if len(components)>4:raise ValueError('Original battle record has four visual component rows')
    if components:b[0xd4]=1
    for index,(item,definition) in enumerate(components):
        struct.pack_into('<8I',b,0xd8+index*32,definition['slot'],*item['identity'],definition.get('visual_source_bank',0),definition['visual_resource'],definition['visual_layer'])
    return bytes(b)
def battle_group_record(profile,background_id):
    b=record(0x58,0x2c)
    struct.pack_into('<II',b,8,*BATTLE_GROUP)
    struct.pack_into('<IIii',b,0x10,background_id,0,800,600)
    struct.pack_into('<hh',b,0x20,*profile.spawn_grid)
    return bytes(b)
def encounter_notice(identity,name,selector_fields,profile,request_id,background_id=15,vitals=None,equipment=()):
    if len(selector_fields)!=248:raise ValueError('Expected preserved selector fields')
    vitals=vitals or {'hp':100,'max_hp':100,'tp':30,'max_tp':30}
    player_appearance=selector_fields[0x30:0x48]
    appearance=bytearray(24);struct.pack_into('<I',appearance,8,BATTLE_ENEMY_BANK)
    tail=battle_group_record(profile,background_id)
    tail+=battle_actor_record(identity,name,player_appearance,1,(-96,0),profile.spawn_grid,profile.map_id,**vitals,controlled=True,equipment=equipment)
    tail+=battle_actor_record(ENEMY_IDENTITY,ENEMY_NAME,bytes(appearance),2,(96,0),enemy_grid(profile),profile.map_id,battle_model_bank=BATTLE_ENEMY_RESOURCE_BANK)
    tail+=bytes(4)
    b=bytearray(message(0x9d,bytes(35+len(tail)),request_id)[:44])
    struct.pack_into('<I',b,12,44+len(tail))
    struct.pack_into('<IIIII',b,16,*identity,profile.map_id,*BATTLE_GROUP)
    return bytes(b)+tail

def enemy_selection_reply(request,profile):
    b=bytearray(message(0xc7,bytes(51),request['request_id']))
    struct.pack_into('<I',b,12,4)
    struct.pack_into('<IIIIIii',b,16,*request['identity'],profile.map_id,*ENEMY_IDENTITY,*enemy_grid(profile))
    # Original 7B3470: exact mask1 executes command20001 -> C8 action1.
    struct.pack_into('<II',b,48,1,0)
    return bytes(b)
def enemy_action_reply(request):
    b=bytearray(message(0xc9,bytes(39),request['request_id']))
    struct.pack_into('<Ii',b,12,0,0)
    struct.pack_into('<IIIIII',b,20,*request['identity'],request['map_id'],*ENEMY_IDENTITY,request['action'])
    return bytes(b)
