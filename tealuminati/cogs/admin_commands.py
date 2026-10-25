import io
import json
import logging
from datetime import datetime

import discord
from discord.ext import commands

from tealuminati import config
from tealuminati.pings import PING_ROLE_LABELS, resolve_ping_mentions
from tealuminati.services.database import get_database
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
        wa = self.bot.get_cog("WaMonitor")
        rmb = self.bot.get_cog("RmbMonitor")
        sse = getattr(self.bot, "sse_client", None)
        sse_status = (
            "Connected" if (sse and sse.is_connected) else ("Reconnecting" if config.SSE_ENABLED else "Disabled")
        )
        fields = {
            "Region": config.REGION_NAME,
            "SSE Stream": sse_status,
            "Checks": str(region.check_count if region else 0),
            "Current Nations": str(len(region.current) if region and region.current else 0),
            "Baseline Nations": str(len(region.baseline) if region else 0),
            "Pending Changes": str(len(region.counters) if region else 0),
            "WA Nations": str(len(wa.baseline) if wa else 0),
            "WA Pending Changes": str(len(wa.counters) if wa else 0),
            "RMB Last Post ID": str(rmb.last_post_id or "None yet") if rmb else "N/A",
            "Database": config.DATABASE_FILE,
        }
        await ctx.send(embed=EmbedBuilder.status_embed(fields))

    @commands.command(name="ssestatus")
    async def ssestatus(self, ctx: commands.Context):
        sse = getattr(self.bot, "sse_client", None)
        if not sse or not config.SSE_ENABLED:
            await ctx.send("SSE streaming is disabled.")
            return
        fields = {
            "Status": "Connected (Live)" if sse.is_connected else "Connecting / Reconnecting",
            "Region": config.REGION_NAME,
            "Last Event ID": str(sse.last_event_id or "None"),
            "Reconnects": str(sse.reconnect_count),
            "Reconcile Interval": f"{config.RECONCILE_INTERVAL}s",
            "Target Buckets": "rmb + move + founding + cte + eject + member",
        }
        await ctx.send(embed=EmbedBuilder.status_embed(fields))

    @commands.command(name="forcecheck")
    async def forcecheck(self, ctx: commands.Context):
        region = self.bot.get_cog("RegionMonitor")
        wa = self.bot.get_cog("WaMonitor")
        if not region and not wa:
            await ctx.send("Monitors are disabled")
            return
        await ctx.send("Checking...")
        parts = []
        if region:
            await region.process_updates()
            parts.append(f"Region nations: {len(region.current)}")
        if wa:
            await wa.process_updates()
            parts.append(f"WA nations: {len(wa.current)}")
        await ctx.send(f"Done! {', '.join(parts)}")

    @commands.command(name="wastatus")
    async def wastatus(self, ctx: commands.Context):
        wa = self.bot.get_cog("WaMonitor")
        if not wa:
            await ctx.send("World Assembly monitor is disabled")
            return
        fields = {
            "Region": config.REGION_NAME,
            "WA Checks": str(wa.check_count),
            "Current WA Nations": str(len(wa.current) if wa.current else 0),
            "Baseline WA Nations": str(len(wa.baseline)),
            "Pending WA Changes": str(len(wa.counters)),
            "Check Interval": f"{config.WA_CHECK_INTERVAL}s",
            "Join Threshold": str(config.WA_JOIN_THRESHOLD),
            "Leave Threshold": str(config.WA_LEAVE_THRESHOLD),
        }
        await ctx.send(embed=EmbedBuilder.status_embed(fields))

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
