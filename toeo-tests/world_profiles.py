"""Explicit world profiles; historical placement is tied to a source and map.

The Rashuan identity is a visual match of original 1120108 minimap pixels to
the named 2006 Wiki map. Merchant XY comes from that Wiki's shop entry.
Entity ID, appearance and navigation remain local reconstruction choices.
"""
from dataclasses import dataclass
from functools import cached_property
import world_map_navigation as forest
import world_rashuan_navigation as rashuan


@dataclass(frozen=True)
class WorldProfile:
    key: str
    map_id: int
    label: str
    spawn_grid: tuple
    merchant_grid: tuple
    merchant_name: str
    navigation: object
    stock_key: str | None = None

    @cached_property
    def slots(self):
        result = bytearray()
        data = self.navigation.NAV_RLE
        for value, count in zip(data[::2], data[1::2]):
            result.extend(bytes((value,))*count)
        if len(result) != self.navigation.NAV_WIDTH*self.navigation.NAV_HEIGHT:
            raise ValueError('Navigation cell count mismatch')
        return bytes(result)

    def in_bounds(self, grid):
        x, y = grid
        return (isinstance(x, int) and isinstance(y, int)
                and 0 <= x < self.navigation.GRID_WIDTH
                and 0 <= y < self.navigation.GRID_HEIGHT and (x-y) % 2 == 0)

    def walkable(self, grid):
        return self.in_bounds(grid) and bool(self.slots[grid[1]*self.navigation.NAV_WIDTH+grid[0]//2])


FOREST = WorldProfile('forest', 0x1110101, 'Local World', (6, 4),
                      (12, 8), 'Archive Shop', forest)
RASHUAN = WorldProfile('rashuan', 0x1120108, 'ラシュアン河の河口', (139, 313),
                       (141, 313), '行商人＜道具屋＞', rashuan, 'wikihouse-u392bcdb')
PROFILES = {profile.key: profile for profile in (FOREST, RASHUAN)}


def world_profile(key='forest'):
    if isinstance(key, WorldProfile):
        return key
    try:
        return PROFILES[key]
    except KeyError:
        raise ValueError('Unknown world profile: '+str(key)) from None
