import asyncio
import logging

from discord.ext import commands, tasks

from tealuminati import config
from tealuminati.pings import PING_ROLE_LABELS
from tealuminati.services.database import get_database
from tealuminati.services.rmb_api import fetch_posts
from tealuminati.views.embeds import EmbedBuilder

log = logging.getLogger(__name__)


class RmbMonitor(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = get_database()
        self.last_post_id: int = self.db.get_meta_int("rmb_last_post_id")

    # ---- background task ----

    @tasks.loop(seconds=config.RECONCILE_INTERVAL if config.SSE_ENABLED else config.RMB_CHECK_INTERVAL)
    async def rmb_poll_task(self):
        await self._check_new_posts()

    @rmb_poll_task.before_loop
    async def before_rmb_poll(self):
        await self.bot.wait_until_ready()
        if getattr(self.bot, "sse_client", None):
            self.bot.sse_client.register_rmb_handler(self.on_sse_post)
        log.info(
            "RMB monitor started (last post id %s, mode: %s)",
            self.last_post_id or "none",
            "SSE" if config.SSE_ENABLED else "polling",
        )

    async def on_sse_post(self, post):
        if self.last_post_id == 0:
            self.last_post_id = post.post_id
            self.db.set_meta("rmb_last_post_id", self.last_post_id)
            log.info("RMB seeded via SSE at post %d", post.post_id)
            return

        if post.post_id <= self.last_post_id:
            return

        await self._notify(post)
        self.last_post_id = post.post_id
        self.db.set_meta("rmb_last_post_id", self.last_post_id)

    async def cog_load(self):
        self.rmb_poll_task.start()

    def cog_unload(self):
        self.rmb_poll_task.cancel()

    # ---- core logic ----

    async def _check_new_posts(self):
        posts = await asyncio.to_thread(fetch_posts, config.REGION_NAME, 5)
        if not posts:
            return

        posts.sort(key=lambda p: p.post_id)
        new_posts = [p for p in posts if p.post_id > self.last_post_id]
        if not new_posts:
            return

        if self.last_post_id == 0:
            newest = new_posts[-1].post_id
            log.info("RMB seeded at post %d (%d existing posts skipped)", newest, len(new_posts))
            self.last_post_id = newest
            self.db.set_meta("rmb_last_post_id", newest)
            return

        for post in new_posts:
            await self._notify(post)

        self.last_post_id = new_posts[-1].post_id
        self.db.set_meta("rmb_last_post_id", self.last_post_id)

    async def _notify(self, post):
        channel = self.bot.get_channel(config.NOTIFICATION_CHANNEL_ID)
        if not channel:
            log.warning("Notification channel %s not found", config.NOTIFICATION_CHANNEL_ID)
            return

        try:
            roles = self.db.load_ping_roles()
            mentions = []
            for slot, role_id in roles.items():
                role = channel.guild.get_role(role_id) if channel.guild else None
                if role:
                    mentions.append(role.mention)
            if mentions:
                await channel.send(" ".join(mentions))
            await channel.send(embed=EmbedBuilder.rmb_embed(post))
        except Exception as exc:
            log.error("RMB notification error: %s", exc)

    # ---- commands ----

    @commands.command(name="rmbstatus")
    async def rmbstatus(self, ctx: commands.Context):
        roles = self.db.load_ping_roles()
        sse = getattr(self.bot, "sse_client", None)
        mode = (
            "SSE Stream (Live)"
            if (config.SSE_ENABLED and sse and sse.is_connected)
            else ("SSE (Connecting)" if config.SSE_ENABLED else "Polling")
        )
        fields = {
            "Mode": mode,
            "Last Post ID": str(self.last_post_id or "None yet"),
            "Poll/Reconcile Interval": f"{config.RECONCILE_INTERVAL if config.SSE_ENABLED else config.RMB_CHECK_INTERVAL}s",
        }
        for slot in config.PING_ROLE_ORDER:
            role_id = roles.get(slot)
            fields[f"Ping: {PING_ROLE_LABELS[slot]}"] = f"<@&{role_id}>" if role_id else "Not set"
        embed = EmbedBuilder.status_embed(fields)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RmbMonitor(bot))
