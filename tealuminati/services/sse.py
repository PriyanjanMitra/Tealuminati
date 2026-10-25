import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Callable, Coroutine

import aiohttp

from tealuminati import config
from tealuminati.models import RmbPost
from tealuminati.services.database import get_database

log = logging.getLogger(__name__)

SSE_BASE_URL = "https://www.nationstates.net/api"
USER_AGENT = "TealuminatiMonitorBot/2.0 (contact: priyanjanmitra@gmail.com)"

RE_POST_ID = re.compile(r"postid=(\d+)")
RE_MOVE = re.compile(r"@@(.*?)@@ relocated from %%(.*?)%% to %%(.*?)%%")
RE_FOUND = re.compile(r"@@(.*?)@@ was (?:re)?founded in %%(.*?)%%")
RE_EJECT = re.compile(r"@@(.*?)@@ was ejected from %%(.*?)%%")
RE_CTE = re.compile(r"@@(.*?)@@ ceased to exist in %%(.*?)%%")
RE_ADMIT = re.compile(r"@@(.*?)@@ was admitted to the World Assembly")
RE_RESIGN = re.compile(r"@@(.*?)@@ resigned from the World Assembly")


class SSEClient:

    def __init__(self, bot=None):
        self.bot = bot
        self.db = get_database()
        self.is_connected = False
        self.last_event_id: str | None = self.db.get_meta("sse_last_event_id")
        self.reconnect_count = 0
        self._task: asyncio.Task | None = None
        self._session: aiohttp.ClientSession | None = None
        self._running = False
        self.region_canonical = config.REGION_NAME.lower().replace(" ", "_")

        self.rmb_handlers: list[Callable[[RmbPost], Coroutine[Any, Any, None]]] = []
        self.region_join_handlers: list[Callable[[str], Coroutine[Any, Any, None]]] = []
        self.region_leave_handlers: list[Callable[[str], Coroutine[Any, Any, None]]] = []
        self.wa_admit_handlers: list[Callable[[str], Coroutine[Any, Any, None]]] = []
        self.wa_resign_handlers: list[Callable[[str], Coroutine[Any, Any, None]]] = []

    def register_rmb_handler(self, handler: Callable[[RmbPost], Coroutine[Any, Any, None]]):
        self.rmb_handlers.append(handler)

    def register_region_join_handler(self, handler: Callable[[str], Coroutine[Any, Any, None]]):
        self.region_join_handlers.append(handler)

    def register_region_leave_handler(self, handler: Callable[[str], Coroutine[Any, Any, None]]):
        self.region_leave_handlers.append(handler)

    def register_wa_admit_handler(self, handler: Callable[[str], Coroutine[Any, Any, None]]):
        self.wa_admit_handlers.append(handler)

    def register_wa_resign_handler(self, handler: Callable[[str], Coroutine[Any, Any, None]]):
        self.wa_resign_handlers.append(handler)

    def _parse_rmb_post(self, event_data: dict) -> RmbPost | None:
        str_text = event_data.get("str", "")
        html_text = event_data.get("htmlStr", "")
        post_match = RE_POST_ID.search(html_text) or RE_POST_ID.search(str_text)
        post_id = int(post_match.group(1)) if post_match else None
        if not post_id:
            try:
                post_id = int(event_data.get("id", 0))
            except ValueError:
                return None

        nation = None
        for b in event_data.get("buckets", []):
            if b.startswith("nation:"):
                nation = b[7:]
                break
        if not nation:
            m = re.search(r"@@(.*?)@@", str_text)
            if m:
                nation = m.group(1)
        if not nation:
            return None

        try:
            timestamp = datetime.fromtimestamp(int(event_data.get("time", datetime.now().timestamp())))
        except (ValueError, TypeError):
            timestamp = datetime.now()

        message = event_data.get("rmbMessage") or ""

        return RmbPost(
            post_id=post_id,
            nation=nation,
            timestamp=timestamp,
            message=message,
            likes=0,
        )

    async def _handle_event(self, event_data: dict):
        event_str = event_data.get("str", "")
        buckets = event_data.get("buckets", [])

        # 1. RMB event
        if "rmb" in buckets or event_data.get("rmbMessage") is not None:
            post = self._parse_rmb_post(event_data)
            if post:
                for handler in self.rmb_handlers:
                    try:
                        await handler(post)
                    except Exception as exc:
                        log.error("Error in RMB SSE handler: %s", exc)

        # 2. Movement / Founding / Departure
        found_match = RE_FOUND.search(event_str)
        if found_match:
            nation, region = found_match.group(1), found_match.group(2)
            if region.lower() == self.region_canonical:
                for handler in self.region_join_handlers:
                    try:
                        await handler(nation)
                    except Exception as exc:
                        log.error("Error in region join handler: %s", exc)

        move_match = RE_MOVE.search(event_str)
        if move_match:
            nation, from_region, to_region = move_match.group(1), move_match.group(2), move_match.group(3)
            if to_region.lower() == self.region_canonical:
                for handler in self.region_join_handlers:
                    try:
                        await handler(nation)
                    except Exception as exc:
                        log.error("Error in region join handler: %s", exc)
            elif from_region.lower() == self.region_canonical:
                for handler in self.region_leave_handlers:
                    try:
                        await handler(nation)
                    except Exception as exc:
                        log.error("Error in region leave handler: %s", exc)

        eject_match = RE_EJECT.search(event_str)
        if eject_match:
            nation, region = eject_match.group(1), eject_match.group(2)
            if region.lower() == self.region_canonical:
                for handler in self.region_leave_handlers:
                    try:
                        await handler(nation)
                    except Exception as exc:
                        log.error("Error in region leave handler: %s", exc)

        cte_match = RE_CTE.search(event_str)
        if cte_match:
            nation, region = cte_match.group(1), cte_match.group(2)
            if region.lower() == self.region_canonical:
                for handler in self.region_leave_handlers:
                    try:
                        await handler(nation)
                    except Exception as exc:
                        log.error("Error in region leave handler: %s", exc)

        # 3. WA Membership
        admit_match = RE_ADMIT.search(event_str)
        if admit_match:
            nation = admit_match.group(1)
            for handler in self.wa_admit_handlers:
                try:
                    await handler(nation)
                except Exception as exc:
                    log.error("Error in WA admit handler: %s", exc)

        resign_match = RE_RESIGN.search(event_str)
        if resign_match:
            nation = resign_match.group(1)
            for handler in self.wa_resign_handlers:
                try:
                    await handler(nation)
                except Exception as exc:
                    log.error("Error in WA resign handler: %s", exc)

    async def _run_stream(self):
        url = f"{SSE_BASE_URL}/rmb+move+founding+cte+eject+member/region:{self.region_canonical}"
        backoff = 2

        while self._running:
            try:
                headers = {"User-Agent": USER_AGENT}
                if self.last_event_id:
                    headers["Last-Event-ID"] = str(self.last_event_id)

                timeout = aiohttp.ClientTimeout(total=None, sock_read=60)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    self._session = session
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            log.warning("SSE connection returned HTTP %s. Retrying in %ss...", resp.status, backoff)
                            await asyncio.sleep(backoff)
                            backoff = min(backoff * 2, 60)
                            continue

                        self.is_connected = True
                        self.reconnect_count += 1
                        backoff = 2
                        log.info("Connected to NationStates Live Happenings SSE stream for %s", config.REGION_NAME)

                        current_id = None
                        data_lines = []

                        async for raw_line in resp.content:
                            line_str = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                            if not line_str:
                                if data_lines:
                                    payload = "\n".join(data_lines)
                                    data_lines = []
                                    try:
                                        data = json.loads(payload)
                                        if current_id:
                                            self.last_event_id = current_id
                                            self.db.set_meta("sse_last_event_id", current_id)
                                        await self._handle_event(data)
                                    except Exception as exc:
                                        log.warning("Failed to parse SSE event JSON: %s", exc)
                                continue

                            if line_str.startswith(":"):
                                continue
                            if line_str.startswith("id:"):
                                current_id = line_str[3:].strip()
                            elif line_str.startswith("data:"):
                                data_lines.append(line_str[5:].strip())

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.is_connected = False
                log.warning("SSE connection error: %s. Reconnecting in %ss...", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
            finally:
                self.is_connected = False

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_stream())
        log.info("SSE client started")

    async def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.is_connected = False
        log.info("SSE client stopped")
