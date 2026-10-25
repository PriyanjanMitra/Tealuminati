import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tealuminati.cogs.wa_monitor import WaMonitor
from tealuminati.services.database import Database
from tealuminati.views.embeds import EmbedBuilder


class WaEmbedTests(unittest.TestCase):
    def test_wa_admitted_embed(self):
        embed = EmbedBuilder.wa_embed("Testlandia", "wa_admitted")
        self.assertEqual(embed.title, "ADMITTED TO WORLD ASSEMBLY")
        self.assertIn("Testlandia has joined the World Assembly!", embed.description)
        self.assertEqual(len(embed.fields), 2)

    def test_wa_resigned_embed(self):
        embed = EmbedBuilder.wa_embed("Testlandia", "wa_resigned")
        self.assertEqual(embed.title, "RESIGNED FROM WORLD ASSEMBLY")
        self.assertIn("Testlandia has resigned from the World Assembly!", embed.description)

    def test_wa_member_joined_region_embed(self):
        embed = EmbedBuilder.wa_embed("Testlandia", "wa_member_joined_region")
        self.assertEqual(embed.title, "WA MEMBER JOINED REGION")
        self.assertIn("(World Assembly member) has entered the region!", embed.description)

    def test_wa_member_left_region_embed(self):
        embed = EmbedBuilder.wa_embed("Testlandia", "wa_member_left_region")
        self.assertEqual(embed.title, "WA MEMBER LEFT REGION")
        self.assertIn("(World Assembly member) has left the region!", embed.description)


class WaMonitorLogicTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(f"{self.tmp.name}/test.db")
        self.bot = MagicMock()
        with patch("tealuminati.cogs.wa_monitor.get_database", return_value=self.db):
            self.cog = WaMonitor(self.bot)
        self.cog._notify = AsyncMock()
        self.cog.check_count = 100  # Outside startup grace period

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_is_in_region_fallback_to_db(self):
        self.bot.get_cog.return_value = None
        self.db.save_baseline({"resident_nation"})
        self.assertTrue(self.cog._is_in_region("resident_nation"))
        self.assertFalse(self.cog._is_in_region("immigrant_nation"))

    def test_is_in_region_via_region_cog(self):
        region_cog = MagicMock()
        region_cog.baseline = {"resident_cog_nation"}
        self.bot.get_cog.return_value = region_cog
        self.assertTrue(self.cog._is_in_region("resident_cog_nation"))
        self.assertFalse(self.cog._is_in_region("other_nation"))

    async def test_initialization_seeds_silently(self):
        with patch("tealuminati.cogs.wa_monitor.fetch_region_wa_nations", return_value={"wa1", "wa2"}):
            await self.cog.process_updates()

        self.assertTrue(self.cog.initialized)
        self.assertEqual(self.cog.baseline, {"wa1", "wa2"})
        self.assertEqual(self.cog.last_baseline_size, 2)
        self.cog._notify.assert_not_called()

    async def test_resident_admitted_to_wa(self):
        # Initial state: initialized with wa1, resident nation is in region baseline
        self.cog.initialized = True
        self.cog.baseline = {"wa1"}
        self.cog.last_baseline_size = 1
        self.db.save_baseline({"resident_nation", "wa1"})
        self.bot.get_cog.return_value = None

        # Reach join threshold (default 3)
        with patch("tealuminati.cogs.wa_monitor.fetch_region_wa_nations", return_value={"wa1", "resident_nation"}):
            for _ in range(3):
                await self.cog.process_updates()

        self.assertIn("resident_nation", self.cog.baseline)
        self.cog._notify.assert_called_with("resident_nation", "wa_admitted")

    async def test_immigrant_wa_member_joined_region(self):
        # Initial state: initialized with wa1, foreign nation is NOT in region baseline
        self.cog.initialized = True
        self.cog.baseline = {"wa1"}
        self.cog.last_baseline_size = 1
        self.db.save_baseline({"wa1"})  # foreign_wa is not in baseline
        self.bot.get_cog.return_value = None

        # Reach join threshold (default 3)
        with patch("tealuminati.cogs.wa_monitor.fetch_region_wa_nations", return_value={"wa1", "foreign_wa"}):
            for _ in range(3):
                await self.cog.process_updates()

        self.assertIn("foreign_wa", self.cog.baseline)
        self.cog._notify.assert_called_with("foreign_wa", "wa_member_joined_region")

    async def test_resident_resigned_from_wa(self):
        # Initial state: initialized with wa1 and wa2. wa2 resigns from WA but is still in region baseline
        self.cog.initialized = True
        self.cog.baseline = {"wa1", "wa2"}
        self.cog.last_baseline_size = 2
        self.db.save_baseline({"wa1", "wa2"})
        self.bot.get_cog.return_value = None

        # Reach leave threshold (default 20)
        with patch("tealuminati.cogs.wa_monitor.fetch_region_wa_nations", return_value={"wa1"}):
            for _ in range(20):
                await self.cog.process_updates()

        self.assertNotIn("wa2", self.cog.baseline)
        self.cog._notify.assert_called_with("wa2", "wa_resigned")

    async def test_wa_member_left_region(self):
        # Initial state: initialized with wa1 and wa2. wa2 left region completely
        self.cog.initialized = True
        self.cog.baseline = {"wa1", "wa2"}
        self.cog.last_baseline_size = 2
        self.db.save_baseline({"wa1"})  # wa2 already removed from region baseline
        self.bot.get_cog.return_value = None

        # Reach leave threshold (default 20)
        with patch("tealuminati.cogs.wa_monitor.fetch_region_wa_nations", return_value={"wa1"}):
            for _ in range(20):
                await self.cog.process_updates()

        self.assertNotIn("wa2", self.cog.baseline)
        self.cog._notify.assert_called_with("wa2", "wa_member_left_region")

    async def test_startup_grace_period_skips_notify(self):
        self.cog.initialized = True
        self.cog.baseline = {"wa1"}
        self.cog.last_baseline_size = 1
        self.cog.check_count = 0  # In startup grace period
        self.db.save_baseline({"resident_nation", "wa1"})
        self.bot.get_cog.return_value = None

        with patch("tealuminati.cogs.wa_monitor.fetch_region_wa_nations", return_value={"wa1", "resident_nation"}):
            for _ in range(3):
                await self.cog.process_updates()

        self.assertIn("resident_nation", self.cog.baseline)
        self.cog._notify.assert_not_called()

    async def test_sanity_check_rejects_sudden_drop(self):
        self.cog.initialized = True
        self.cog.baseline = {f"wa{i}" for i in range(20)}
        self.cog.last_baseline_size = 20

        # Drop from 20 to 2 (< 50% of baseline)
        with patch("tealuminati.cogs.wa_monitor.fetch_region_wa_nations", return_value={"wa0", "wa1"}):
            await self.cog.process_updates()

        # Baseline should be unchanged and no counters added
        self.assertEqual(len(self.cog.baseline), 20)
        self.assertEqual(self.cog.counters, {})

    async def test_notify_sends_role_pings_and_embed(self):
        channel = MagicMock()
        channel.send = AsyncMock()
        guild = MagicMock()
        channel.guild = guild

        role = MagicMock()
        role.mention = "<@&123456789>"
        guild.get_role.return_value = role

        self.bot.get_channel.return_value = channel

        real_notify = WaMonitor._notify
        with patch.object(self.cog.db, "load_ping_roles", return_value={"home": 123456789}):
            await real_notify(self.cog, "Testlandia", "wa_admitted")

        self.assertEqual(channel.send.call_count, 2)
        channel.send.assert_any_call("<@&123456789>")


if __name__ == "__main__":
    unittest.main()
