import discord

from tealuminati.config import REGION_NAME


def _region_url() -> str:
    return f"https://www.nationstates.net/region={REGION_NAME.lower().replace(' ', '_')}"


def _nation_url(nation_name: str) -> str:
    return f"https://www.nationstates.net/nation={nation_name.lower().replace(' ', '_')}"


class EmbedBuilder:

    @staticmethod
    def join_embed(nation_name: str) -> discord.Embed:
        embed = discord.Embed(
            title="NEW NATION JOINED",
            description=f"{nation_name} has entered the region!",
            color=discord.Color.green(),
        )
        embed.add_field(name="Nation", value=f"[Click to view]({_nation_url(nation_name)})", inline=False)
        embed.add_field(name="Region", value=f"[Click to view]({_region_url()})", inline=True)
        return embed

    @staticmethod
    def leave_embed(nation_name: str) -> discord.Embed:
        embed = discord.Embed(
            title="NATION LEFT",
            description=f"{nation_name} has left the region!",
            color=discord.Color.red(),
        )
        embed.add_field(name="Nation", value=f"[Click to view]({_nation_url(nation_name)})", inline=False)
        embed.add_field(name="Region", value=f"[Click to view]({_region_url()})", inline=True)
        return embed

    @staticmethod
    def rmb_embed(post) -> discord.Embed:
        content = post.message[:500]
        if len(post.message) > 500:
            content += "…"
        embed = discord.Embed(
            title="NEW RMB POST",
            description=f"{post.nation} posted on the Regional Message Board",
            color=discord.Color.blue(),
            url=_region_url(),
        )
        embed.add_field(name="Nation", value=post.nation, inline=True)
        embed.add_field(name="Likes", value=str(post.likes), inline=True)
        embed.add_field(name="Message", value=f"```{content}```", inline=False)
        embed.timestamp = post.timestamp
        return embed

    @staticmethod
    def status_embed(fields: dict[str, str]) -> discord.Embed:
        embed = discord.Embed(title="Bot Status", color=discord.Color.blue())
        for name, value in fields.items():
            embed.add_field(name=name, value=value)
        return embed
