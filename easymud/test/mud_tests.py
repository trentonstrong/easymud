import unittest
from simplemud.mud import World, Room


class TestRooms(unittest.TestCase):
    """
    Test the room building algorithm
    """

    def setUp(self):
        self.rooms = {
            "test1": {
                "title": "A test room",
                "description": "hello world!",
                "exits": {
                    "north": "test1"
                }
            }
        }

    def test_build_rooms(self):
        rooms = World(self.rooms)
        self.assertTrue(isinstance(rooms.get('test1'), Room))
