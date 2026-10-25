import asyncio
import logging
import time

from discord.ext import commands, tasks

from tealuminati import config
from tealuminati.pings import resolve_ping_mentions
from tealuminati.services.database import get_database
from tealuminati.services.nations_api import fetch_region_wa_nations
from tealuminati.services.region_logic import can_notify, confirm_changes, update_counters
from tealuminati.views.embeds import EmbedBuilder

log = logging.getLogger(__name__)


class WaMonitor(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = get_database()
        self.current: set[str] = set()
        self.baseline: set[str] = self.db.load_wa_baseline()
        self.counters: dict[str, int] = self.db.load_wa_stability()
        self.notified: dict[str, float] = self.db.load_wa_notified()
        self.check_count: int = self.db.get_meta_int("wa_check_count")
        self.initialized: bool = bool(self.db.get_meta_int("wa_initialized"))
        self.last_baseline_size: int = self.db.get_meta_int("last_wa_baseline_size")

    # ---- background task ----

    @tasks.loop(seconds=config.WA_CHECK_INTERVAL)
    async def monitoring_task(self):
        await self.process_updates()

    @monitoring_task.before_loop
    async def before_monitoring(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)
        log.info("World Assembly monitor started (%s baseline WA nations)", len(self.baseline))

    async def cog_load(self):
        self.monitoring_task.start()

    def cog_unload(self):
        self.monitoring_task.cancel()

    # ---- core logic ----

    def _is_in_region(self, nation: str) -> bool:
        region_cog = self.bot.get_cog("RegionMonitor")
        if region_cog and region_cog.baseline:
            return nation in region_cog.baseline
        return nation in self.db.load_baseline()

    async def process_updates(self):
        current = await asyncio.to_thread(fetch_region_wa_nations, config.REGION_NAME)
        if current is None:
            return

        if self.initialized and self.last_baseline_size > config.WA_SANITY_MIN_BASELINE:
            ratio = len(current) / self.last_baseline_size
            if ratio < config.WA_SANITY_MIN_RATIO:
                log.warning(
                    "Rejecting WA API result (%d nations vs baseline %d, ratio=%.2f)",
                    len(current), self.last_baseline_size, ratio,
                )
                return

        self.current = current

        if not self.initialized:
            self.baseline = set(current)
            self.counters.clear()
            self.initialized = True
            self.last_baseline_size = len(current)
            self._persist()
            log.info("World Assembly monitor initialized: %d nations", len(current))
            return

        added = current - self.baseline
        removed = self.baseline - current

        if added or removed or self.counters:
            update_counters(self.counters, added, removed)
            await self._confirm_and_notify()
            self._persist()
        elif self.check_count % 10 == 0:
            log.info("Heartbeat: %d WA nations stable", len(self.baseline))

        self.check_count += 1
        self.db.set_meta("wa_check_count", self.check_count)

    async def _confirm_and_notify(self):
        joins, leaves = confirm_changes(self.counters, config.WA_JOIN_THRESHOLD, config.WA_LEAVE_THRESHOLD)
        now = time.time()
        in_grace = self.check_count < config.WA_STARTUP_GRACE_CHECKS

        for nation in joins:
            self.baseline.add(nation)
            del self.counters[nation]
            if in_grace:
                log.info("Grace period: skipping WA notify for %s", nation)
            elif can_notify(self.notified.get(nation), now, config.NOTIFY_COOLDOWN_SECONDS):
                event_type = "wa_admitted" if self._is_in_region(nation) else "wa_member_joined_region"
                await self._notify(nation, event_type)
                self.notified[nation] = now
                self.db.record_wa_notified(nation, now)
            else:
                log.info("Cooldown: skipping duplicate WA join notify for %s", nation)

        for nation in leaves:
            self.baseline.discard(nation)
            del self.counters[nation]
            if can_notify(self.notified.get(nation), now, config.NOTIFY_COOLDOWN_SECONDS):
                event_type = "wa_resigned" if self._is_in_region(nation) else "wa_member_left_region"
                await self._notify(nation, event_type)
                self.notified[nation] = now
                self.db.record_wa_notified(nation, now)
            else:
                log.info("Cooldown: skipping duplicate WA leave notify for %s", nation)

        if joins or leaves:
            self.last_baseline_size = len(self.baseline)
            self._prune_notified(now)

    def _prune_notified(self, now: float):
        cutoff = now - config.NOTIFY_COOLDOWN_SECONDS
        stale = [n for n, ts in self.notified.items() if ts < cutoff]
        for nation in stale:
            del self.notified[nation]
        if stale:
            self.db.prune_wa_notified(cutoff)

    # ---- persistence ----

    def _persist(self):
        self.db.save_wa_baseline(self.baseline)
        self.db.save_wa_stability(self.counters)
        self.db.set_meta("wa_initialized", int(self.initialized))
        self.db.set_meta("last_wa_baseline_size", self.last_baseline_size)

    # ---- notification ----

    async def _notify(self, nation_name: str, event_type: str):
        channel = self.bot.get_channel(config.NOTIFICATION_CHANNEL_ID)
        if not channel:
            log.warning("Notification channel %s not found", config.NOTIFICATION_CHANNEL_ID)
            return

        embed = EmbedBuilder.wa_embed(nation_name, event_type)

        try:
            roles = self.db.load_ping_roles()
            pings = " ".join(resolve_ping_mentions(channel.guild, roles))
            if pings:
                await channel.send(pings)
            await channel.send(embed=embed)
        except Exception as exc:
            log.error("WA notification error: %s", exc)


async def setup(bot: commands.Bot):
    await bot.add_cog(WaMonitor(bot))
