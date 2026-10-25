import logging
import xml.etree.ElementTree as ET

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://www.nationstates.net/cgi-bin/api.cgi"
USER_AGENT = "TealuminatiMonitorBot/2.0"
TIMEOUT = 10


def parse_nations(payload: bytes, tag: str = "NATIONS") -> set[str]:
    root = ET.fromstring(payload)
    element = root.find(tag)
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


def parse_wa_nations(payload: bytes) -> set[str]:
    # NationStates uses the legacy <UNNATIONS> XML tag for the wanations shard
    nations = parse_nations(payload, tag="UNNATIONS")
    if not nations:
        nations = parse_nations(payload, tag="WANATIONS")
    return nations


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


def fetch_region_wa_nations(region_name: str) -> set[str] | None:
    try:
        response = requests.get(
            BASE_URL,
            params={"region": region_name, "q": "wanations"},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            return parse_wa_nations(response.content)
        log.warning("WA Nations API returned HTTP %s", response.status_code)
    except Exception as exc:
        log.error("WA Nations API error: %s", exc)
    return None
