import random
import discord

from discord.ext import commands
from phelper.bot import PotiaBot


class PotiaFunStuff(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot

    @commands.command(aliases=["tanyaustaz"])
    async def tanyaustad(self, ctx: commands.Context, *, pertanyaan: str):
        if not pertanyaan:
            return await ctx.send("Mohon berikan pertanyaan untuk pak Ustad")

        SENTIMEN_PAK_USTAD = {
            "positif": [
                "Bisa jadi.",
                "Lah iya juga.",
                "Insyaallah, akan diterima.",
                "Apa pun bisa terjadi asal ada niat dan tekun.",
                "Ingfo diterima. Semoga hari Anda menyenangkan.",
                "Masyaallah, akhi.",
                "Menggokil.",
                "Semoga Allah SWT memberkati harimu, saudaraku.",
            ],
            "netral": [
                "Ini bukan ranah saya, coba tanya Pak Haji.",
                "Be-Betsuni, saya sebagai ustaz tidak tertawa membaca ini. Wkwkwkwkwk",
                "Kenapa kamu tanya begitu?",
                "Ini nih badut sejati",
                "Afkh?",
                "....",
                "Gini amat jadi Pak Ustaz.",
                "Gak tahu. Tandai aja langsung Pak Ustaznya.",
            ],
            "negatif": [
                "Gak 'gitu, woi!",
                "ALLAHUAKBAR!",
                "Dahlah, ckptw.",
                "Perlu diketahui syarat bertanya adalah berakal, sedangkan Anda tidak.",
                "Mangsut amat.",
                "Ngasih pertanyaan logis dikit napa?!",
                "No ingfo.",
                "Ckpsbrdnmngrt.",
                "Lawak lo, badut!",
                "Allahuakbar, Ya Rabbi ....",
            ],
        }
        SENTIMEN_POSITIF = ["positif"] * 120
        SENTIMEN_NETRAL = ["netral"] * 67
        SENTIMEN_NEGATIF = ["negatif"] * 63

        SEMUA_SENTIMEN = SENTIMEN_POSITIF + SENTIMEN_NETRAL + SENTIMEN_NEGATIF

        for _ in range(random.randint(3, 10)):  # nosec
            random.shuffle(SEMUA_SENTIMEN)

        sentimen_akhir = SEMUA_SENTIMEN[random.randint(0, len(SEMUA_SENTIMEN) - 1)]
        sentimen_pilihan = SENTIMEN_PAK_USTAD[sentimen_akhir]
        for _ in range(random.randint(3, 10)):  # nosec
            random.shuffle(sentimen_pilihan)

        embed = discord.Embed(color=discord.Color.random(), timestamp=self.bot.now())
        embed.set_author(name="Pak Ustaz", url="https://p.ihateani.me/mcxcaaft.png")
        embed.set_thumbnail(url="https://p.ihateani.me/mcxcaaft.png")
        embed.description = f"**Pertanyaan**: {pertanyaan}\n\n{random.choice(sentimen_pilihan)}"
        embed.set_footer(text=f"{ctx.author}")

        await ctx.send(embed=embed, reference=ctx.message)


def setup(bot: PotiaBot):
    bot.add_cog(PotiaFunStuff(bot))
