import logging
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from tealuminati.models import RmbPost
from tealuminati.services.nations_api import BASE_URL, USER_AGENT, TIMEOUT

log = logging.getLogger(__name__)


def parse_posts(payload: bytes) -> list[RmbPost]:
    root = ET.fromstring(payload)
    messages = root.find("MESSAGES")
    if messages is None:
        return []

    posts: list[RmbPost] = []
    for elem in messages.findall("POST"):
        nation = elem.findtext("NATION")
        timestamp = elem.findtext("TIMESTAMP")
        if not nation or not timestamp:
            continue
        posts.append(
            RmbPost(
                post_id=int(elem.get("id", 0)),
                nation=nation,
                timestamp=datetime.fromtimestamp(int(timestamp)),
                message=elem.findtext("MESSAGE") or "",
                likes=int(elem.findtext("LIKES") or 0),
            )
        )
    return posts


def fetch_posts(region_name: str, limit: int = 5) -> list[RmbPost] | None:
    try:
        response = requests.get(
            BASE_URL,
            params={"region": region_name, "q": f"messages;limit={limit}"},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            return parse_posts(response.content)
        log.warning("RMB API returned HTTP %s", response.status_code)
    except Exception as exc:
        log.error("RMB API error: %s", exc)
    return None
