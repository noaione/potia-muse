from discord.ext import commands

from phelper.bot import PotiaBot


class MusikTemp(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot

    @commands.command(name="musik", aliases=["m", "music"])
    async def musik_placeholder(self, ctx: commands.Context, *, blackhole: str):
        await ctx.send(
            "Perintah musik Potia dipindahkan ke naoTimes!\n"
            "Info lebih lanjut: <https://naoti.me/docs/perintah/musik>\n\n"
            "Semua perintah tetap sama tanpa perubahan, kecuali anda harus gunakan prefix naoTimes"
            " sekarang, bukan prefix Potia"
        )


def setup(bot: PotiaBot):
    bot.add_cog(MusikTemp(bot))
