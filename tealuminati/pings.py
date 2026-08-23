import discord

from tealuminati.config import PING_ROLE_ORDER

PING_ROLE_LABELS = {
    "home": "Home Office",
    "deputy": "Deputy PM",
    "prime_minister": "Prime Minister",
    "cabinet_secretary": "Cabinet Secretary",
}


def resolve_ping_mentions(guild: discord.Guild | None, roles: dict[str, int]) -> list[str]:
    if not guild:
        return []
    mentions: list[str] = []
    for slot in PING_ROLE_ORDER:
        role_id = roles.get(slot)
        role = guild.get_role(role_id) if role_id else None
        if role:
            mentions.append(role.mention)
    return mentions
