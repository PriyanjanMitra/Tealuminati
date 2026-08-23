import logging

import discord
from discord.ext import commands

from tealuminati import config
from tealuminati.services.database import get_database

log = logging.getLogger(__name__)


class TealuminatiBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = get_database()

    async def setup_hook(self):
        if config.REGION_MONITOR_ENABLED:
            from tealuminati.cogs.region_monitor import RegionMonitor
            from tealuminati.cogs.admin_commands import AdminCommands
            await self.add_cog(RegionMonitor(self))
            await self.add_cog(AdminCommands(self))
        from tealuminati.cogs.rmb_monitor import RmbMonitor
        await self.add_cog(RmbMonitor(self))


def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not config.DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set (add it to .env)")

    if config.KEEP_ALIVE_ENABLED:
        from tealuminati.keep_alive import start_keep_alive
        start_keep_alive()

    TealuminatiBot().run(config.DISCORD_TOKEN)
