"""Explicit offline encounter fixture using original CRSD E000 model bank 100.
Entity, placement and HP are local test values, not official spawn metadata.
Original 51C1E0 parses 22 actor and 2E enemy extension; no client-state writes.
"""
import struct
from account_packets import message
from world_map_packets import record
from character_mutation_packets import encode_name
ENEMY_IDENTITY=(0x72000001,1)
ENEMY_NAME='E000 Local Test'
ENEMY_MODEL_BANK=100
def enemy_grid(profile):
    x,y=profile.spawn_grid
    grid=(x-2,y)
    if not profile.walkable(grid):raise ValueError('Encounter fixture requires an original walkable cell')
    return grid
def enemy_actor_records(profile):
    b=record(0x22,0xd0)
    struct.pack_into('<I',b,4,2)
    struct.pack_into('<II',b,12,*ENEMY_IDENTITY)
    struct.pack_into('<hh',b,0x18,*enemy_grid(profile))
    struct.pack_into('<h',b,0x1c,1)
    b[0x23]=0xff
    b[0x24:0x28]=bytes((1,0,0,1))
    b[0x30:0x74]=encode_name(ENEMY_NAME)
    # Non-humanoid appearance+8 selects CRSD via 501574 -> 4D9B90.
    struct.pack_into('<I',b,0x7c,ENEMY_MODEL_BANK)
    struct.pack_into('<IIII',b,0x8c,100,100,0,0)
    ext=record(0x2e,0x34)
    struct.pack_into('<i',ext,4,-1)
    struct.pack_into('<h',ext,0x16,2)
    # Original 51C89C -> 50E050 creates kind1 at vtable6EEBE4.
    return bytes(b)+bytes(ext)+bytes(4)
def enemy_actor_notice(profile):
    tail=enemy_actor_records(profile)
    b=bytearray(message(0x3b,bytes(23+len(tail)),0xffff)[:32])
    struct.pack_into('<I',b,12,32+len(tail))
    struct.pack_into('<III',b,20,*ENEMY_IDENTITY,profile.map_id)
    return bytes(b)+tail
