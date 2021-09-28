from discord.ext import commands
from phelper.bot import PotiaBot


class PotiaFunStuff(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot

    @commands.command(aliases=["tanyaustaz"])
    async def tanyaustad(self, ctx: commands.Context, *, pertanyaan: str):
        if not pertanyaan:
            return await ctx.send("Mohon berikan pertanyaan untuk pak Ustad")

        await ctx.send(f"Pak <@579438382162378752>, ada yang mau tanya, nih.\n{pertanyaan}")


def setup(bot: PotiaBot):
    bot.add_cog(PotiaFunStuff(bot))
