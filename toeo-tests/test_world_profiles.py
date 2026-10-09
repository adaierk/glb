"""Prevent profile/map confusion and preserve the existing forest save."""
import struct
import tempfile
import unittest
from pathlib import Path
from character_mutation_packets import create_character_request
from local_account_server import AccountStore
from character_store import CharacterStore
from world_position_store import WorldPositionStore
from world_profiles import FOREST, RASHUAN
from world_map_packets import world_map_ready_reply
from world_npc_packets import shop_actor_notice


class WorldProfileTests(unittest.TestCase):
    def test_native_navigation_size_and_historical_coordinate(self):
        self.assertEqual(len(RASHUAN.slots), 144000)
        self.assertTrue(RASHUAN.walkable((141, 313)))
        self.assertTrue(RASHUAN.walkable(RASHUAN.spawn_grid))
        self.assertFalse(RASHUAN.walkable((141, 312)))
        self.assertFalse(RASHUAN.walkable((451, 313)))
        ready = world_map_ready_reply(1, RASHUAN.map_id, RASHUAN.navigation)
        self.assertEqual(struct.unpack_from('<I', ready, 44)[0], 144000)
        self.assertEqual(struct.unpack_from('<I', ready, 36)[0], 0x1120108)
        actor = shop_actor_notice(RASHUAN)
        self.assertEqual(struct.unpack_from('<hh', actor, 32+0x18), (141, 313))
        self.assertEqual(struct.unpack_from('<I', actor, 28)[0], 0x1120108)

    def test_saves_remain_separate_and_reject_other_map(self):
        with tempfile.TemporaryDirectory() as directory:
            accounts = AccountStore(Path(directory)/'accounts.sqlite')
            try:
                identity = CharacterStore(accounts).create(1, create_character_request('Archive'))
                forest = WorldPositionStore(accounts, FOREST)
                river = WorldPositionStore(accounts, RASHUAN)
                forest.save(1, identity, FOREST.map_id, (19, 7))
                self.assertEqual(river.load(1, identity)['grid'], (139, 313))
                river.save(1, identity, RASHUAN.map_id, (143, 313))
                self.assertEqual(forest.load(1, identity)['grid'], (19, 7))
                self.assertEqual(river.load(1, identity)['grid'], (143, 313))
                with self.assertRaises(ValueError):
                    river.save(1, identity, FOREST.map_id, (143, 313))
                with self.assertRaises(ValueError):
                    river.save(2, identity, RASHUAN.map_id, (143, 313))
                CharacterStore(accounts).delete(1, identity)
                self.assertEqual(accounts.db.execute('SELECT COUNT(*) FROM world_positions').fetchone()[0], 0)
                self.assertEqual(accounts.db.execute('SELECT COUNT(*) FROM world_profile_positions').fetchone()[0], 0)
            finally:
                accounts.close()


if __name__ == '__main__':
    unittest.main()
