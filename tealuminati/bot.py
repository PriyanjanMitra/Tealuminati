import logging

import discord
from discord.ext import commands

from tealuminati import config
from tealuminati.services.database import get_database
from tealuminati.services.sse import SSEClient

log = logging.getLogger(__name__)


class TealuminatiBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = get_database()
        self.sse_client = SSEClient(self)

    async def setup_hook(self):
        if config.REGION_MONITOR_ENABLED:
            from tealuminati.cogs.region_monitor import RegionMonitor
            await self.add_cog(RegionMonitor(self))
        if config.WA_MONITOR_ENABLED:
            from tealuminati.cogs.wa_monitor import WaMonitor
            await self.add_cog(WaMonitor(self))
        from tealuminati.cogs.rmb_monitor import RmbMonitor
        await self.add_cog(RmbMonitor(self))
        from tealuminati.cogs.admin_commands import AdminCommands
        await self.add_cog(AdminCommands(self))

        if config.SSE_ENABLED:
            await self.sse_client.start()

    async def close(self):
        if self.sse_client:
            await self.sse_client.stop()
        await super().close()


def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not config.DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set (add it to .env)")

    if config.KEEP_ALIVE_ENABLED:
        from tealuminati.keep_alive import start_keep_alive
        start_keep_alive()

    TealuminatiBot().run(config.DISCORD_TOKEN)
