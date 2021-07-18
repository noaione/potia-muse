import discord
from discord.ext import commands
from phelper.bot import PotiaBot


class BotMetaCommands(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot

    @commands.command(name="info")
    async def meta_info(self, ctx: commands.Context):
        embed = discord.Embed(title="potia (po.tia)", color=discord.Color.random())
        embed.description = "*(n) (Cn)* mandor; pengawas."

        inf = "Sebuah bot yang membantu berbagai hal di peladen resmi Muse Indonesia!\n"
        inf += "Bot ini akan membantu posting episode terbaru ke <#864018911884607508> "
        inf += "dan informasi dari YouTube ke <#864043313166155797>."
        inf += "\nGambar profil: <https://youtu.be/AsWZR2ZTMBM?t=282>"
        inf += "\n\n*[Source Code](https://github.com/noaione/potia-muse)*"
        embed.add_field(name="Info singkat", value=inf, inline=False)
        embed.add_field(name="Versi", value=f"v{self.bot.semver}", inline=False)
        avatar: discord.ClientUser = self.bot.user
        embed.set_thumbnail(url=str(avatar.avatar_url))
        await ctx.send(embed=embed)


def setup(bot: PotiaBot):
    bot.add_cog(BotMetaCommands(bot))
