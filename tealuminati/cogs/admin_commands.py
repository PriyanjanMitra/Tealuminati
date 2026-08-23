import io
import json
import logging
from datetime import datetime

import discord
from discord.ext import commands

from tealuminati import config
from tealuminati.pings import PING_ROLE_LABELS, resolve_ping_mentions
from tealuminati.views.embeds import EmbedBuilder

log = logging.getLogger(__name__)


class AdminCommands(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = get_database()

    # ---- listeners ----

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Bot ready as %s", self.bot.user)
        await self.bot.change_presence(activity=discord.Game(name=f"Monitoring {config.REGION_NAME}"))

    # ---- commands ----

    @commands.command(name="status")
    async def status(self, ctx: commands.Context):
        region = self.bot.get_cog("RegionMonitor")
        rmb = self.bot.get_cog("RmbMonitor")
        fields = {
            "Region": config.REGION_NAME,
            "Checks": str(region.check_count if region else 0),
            "Current Nations": str(len(region.current) if region and region.current else 0),
            "Baseline Nations": str(len(region.baseline) if region else 0),
            "Pending Changes": str(len(region.counters) if region else 0),
            "RMB Last Post ID": str(rmb.last_post_id or "None yet") if rmb else "N/A",
            "Database": config.DATABASE_FILE,
        }
        await ctx.send(embed=EmbedBuilder.status_embed(fields))

    @commands.command(name="forcecheck")
    async def forcecheck(self, ctx: commands.Context):
        monitor = self.bot.get_cog("RegionMonitor")
        if not monitor:
            await ctx.send("Region monitor is disabled")
            return
        await ctx.send("Checking...")
        await monitor.process_updates()
        await ctx.send(f"Done! Current nations: {len(monitor.current)}")

    @commands.command(name="backupnow")
    @commands.has_permissions(administrator=True)
    async def backupnow(self, ctx: commands.Context):
        monitor = self.bot.get_cog("RegionMonitor")
        if not monitor or not monitor.current:
            await ctx.send("No data available")
            return

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "region": config.REGION_NAME,
            "nations_count": len(monitor.baseline),
            "nations": sorted(monitor.baseline),
            "check_count": monitor.check_count,
        }
        payload = json.dumps(snapshot, indent=2).encode()
        file = discord.File(io.BytesIO(payload), filename="known_nations_backup.json")
        await ctx.send(f"Backup: {len(monitor.baseline)} nations", file=file)

    @commands.command(name="setpingroles")
    @commands.has_permissions(administrator=True)
    async def setpingroles(
        self,
        ctx: commands.Context,
        home: discord.Role = None,
        deputy: discord.Role = None,
        pm: discord.Role = None,
        cabinet: discord.Role = None,
    ):
        updates = {
            "home": home,
            "deputy": deputy,
            "prime_minister": pm,
            "cabinet_secretary": cabinet,
        }
        for slot, role in updates.items():
            if role:
                self.db.set_ping_role(slot, role.id)

        roles = self.db.load_ping_roles()
        lines = [
            f"{PING_ROLE_LABELS[slot]}: {f'<@&{roles[slot]}>' if roles.get(slot) else 'Not set'}"
            for slot in config.PING_ROLE_ORDER
        ]
        embed = EmbedBuilder.status_embed({"Ping Roles (shared by both monitors)": "\n".join(lines)})
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommands(bot))
