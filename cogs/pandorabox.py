import discord
from discord.ext import commands
from phelper.bot import PotiaBot


class OwnerPandoraBox(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def reserve(self, ctx: commands.Context, text: str):
        channel_data: discord.TextChannel = ctx.channel
        text = text.lower()
        if "embed" in text:
            embed = discord.Embed()
            embed.description = "*Reserved for later usage*"
            await channel_data.send(embed=embed)
        else:
            await channel_data.send(content="*Reserved for later usage*")


def setup(bot: PotiaBot):
    bot.add_cog(OwnerPandoraBox(bot))
