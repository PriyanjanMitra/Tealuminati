import logging
import xml.etree.ElementTree as ET

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://www.nationstates.net/cgi-bin/api.cgi"
USER_AGENT = "TealuminatiMonitorBot/2.0"
TIMEOUT = 10


def parse_nations(payload: bytes) -> set[str]:
    root = ET.fromstring(payload)
    element = root.find("NATIONS")
    if element is None or not element.text:
        return set()
    text = element.text.strip()
    if not text:
        return set()
    if "," in text:
        return {n.strip() for n in text.split(",") if n.strip()}
    if ":" in text:
        return {n.strip() for n in text.split(":") if n.strip()}
    return {text}


def fetch_region_nations(region_name: str) -> set[str] | None:
    try:
        response = requests.get(
            BASE_URL,
            params={"region": region_name, "q": "nations"},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            return parse_nations(response.content)
        log.warning("Nations API returned HTTP %s", response.status_code)
    except Exception as exc:
        log.error("Nations API error: %s", exc)
    return None
