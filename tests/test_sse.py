import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from tealuminati.services.database import Database
from tealuminati.services.sse import SSEClient


class SSEClientTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(f"{self.tmp.name}/test.db")
        with patch("tealuminati.services.sse.get_database", return_value=self.db):
            self.client = SSEClient()
        self.client.region_canonical = "britannia"

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_parse_rmb_post_valid(self):
        event = {
            "id": "100",
            "time": "1700000000",
            "buckets": ["nation:test_nation", "region:britannia", "rmb"],
            "htmlStr": '<a href="/region=britannia/page=display_region_rmb?postid=5555#p5555">a message</a>',
            "str": '@@test_nation@@ lodged a message on the Regional Message Board',
            "rmbMessage": "Hello Britannia!",
        }
        post = self.client._parse_rmb_post(event)
        self.assertIsNotNone(post)
        self.assertEqual(post.post_id, 5555)
        self.assertEqual(post.nation, "test_nation")
        self.assertEqual(post.message, "Hello Britannia!")

    def test_parse_rmb_post_fallback_post_id(self):
        event = {
            "id": "7777",
            "time": "1700000000",
            "buckets": ["nation:test_nation", "region:britannia", "rmb"],
            "str": '@@test_nation@@ lodged a message',
            "rmbMessage": "Fallback ID test",
        }
        post = self.client._parse_rmb_post(event)
        self.assertIsNotNone(post)
        self.assertEqual(post.post_id, 7777)

    async def test_handle_rmb_event(self):
        handler = AsyncMock()
        self.client.register_rmb_handler(handler)

        event = {
            "id": "101",
            "time": "1700000000",
            "buckets": ["nation:poster", "region:britannia", "rmb"],
            "htmlStr": '<a href="...postid=999#p999">message</a>',
            "rmbMessage": "Greetings!",
        }
        await self.client._handle_event(event)

        handler.assert_called_once()
        called_post = handler.call_args[0][0]
        self.assertEqual(called_post.post_id, 999)
        self.assertEqual(called_post.nation, "poster")

    async def test_handle_founding_join(self):
        join_handler = AsyncMock()
        self.client.register_region_join_handler(join_handler)

        event = {
            "id": "102",
            "buckets": ["founding", "region:britannia"],
            "str": "@@new_colony@@ was founded in %%britannia%%.",
        }
        await self.client._handle_event(event)
        join_handler.assert_called_once_with("new_colony")

    async def test_handle_founding_other_region_ignored(self):
        join_handler = AsyncMock()
        self.client.register_region_join_handler(join_handler)

        event = {
            "id": "103",
            "buckets": ["founding", "region:the_pacific"],
            "str": "@@foreign_colony@@ was founded in %%the_pacific%%.",
        }
        await self.client._handle_event(event)
        join_handler.assert_not_called()

    async def test_handle_move_join(self):
        join_handler = AsyncMock()
        self.client.register_region_join_handler(join_handler)

        event = {
            "id": "104",
            "buckets": ["move"],
            "str": "@@traveler@@ relocated from %%lazarus%% to %%britannia%%.",
        }
        await self.client._handle_event(event)
        join_handler.assert_called_once_with("traveler")

    async def test_handle_move_leave(self):
        leave_handler = AsyncMock()
        self.client.register_region_leave_handler(leave_handler)

        event = {
            "id": "105",
            "buckets": ["move"],
            "str": "@@emigrant@@ relocated from %%britannia%% to %%balder%%.",
        }
        await self.client._handle_event(event)
        leave_handler.assert_called_once_with("emigrant")

    async def test_handle_eject_leave(self):
        leave_handler = AsyncMock()
        self.client.register_region_leave_handler(leave_handler)

        event = {
            "id": "106",
            "buckets": ["eject"],
            "str": "@@rogue@@ was ejected from %%britannia%% by @@delegate@@.",
        }
        await self.client._handle_event(event)
        leave_handler.assert_called_once_with("rogue")

    async def test_handle_cte_leave(self):
        leave_handler = AsyncMock()
        self.client.register_region_leave_handler(leave_handler)

        event = {
            "id": "107",
            "buckets": ["cte"],
            "str": "@@ghost@@ ceased to exist in %%britannia%%.",
        }
        await self.client._handle_event(event)
        leave_handler.assert_called_once_with("ghost")

    async def test_handle_wa_admit(self):
        admit_handler = AsyncMock()
        self.client.register_wa_admit_handler(admit_handler)

        event = {
            "id": "108",
            "buckets": ["member"],
            "str": "@@new_wa@@ was admitted to the World Assembly.",
        }
        await self.client._handle_event(event)
        admit_handler.assert_called_once_with("new_wa")

    async def test_handle_wa_resign(self):
        resign_handler = AsyncMock()
        self.client.register_wa_resign_handler(resign_handler)

        event = {
            "id": "109",
            "buckets": ["member"],
            "str": "@@former_wa@@ resigned from the World Assembly.",
        }
        await self.client._handle_event(event)
        resign_handler.assert_called_once_with("former_wa")


if __name__ == "__main__":
    unittest.main()
