import logging
import time

import discord
from discord.ext import commands
from phelper.bot import PotiaBot


def ping_emote(t_t):
    if t_t < 50:
        emote = ":race_car:"
    elif t_t >= 50 and t_t < 200:
        emote = ":blue_car:"
    elif t_t >= 200 and t_t < 500:
        emote = ":racehorse:"
    elif t_t >= 200 and t_t < 500:
        emote = ":runner:"
    elif t_t >= 500 and t_t < 3500:
        emote = ":walking:"
    elif t_t >= 3500:
        emote = ":snail:"
    return emote


class BotMetaCommands(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("Cogs.MetaCommands")

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
        embed.set_thumbnail(url=str(avatar.avatar))
        await ctx.send(embed=embed)

    @commands.command(name="ping")
    async def meta_ping(self, ctx: commands.Context):
        channel: discord.TextChannel = ctx.channel
        self.logger.info("checking websocket...")
        ws_ping = self.bot.latency
        irnd = lambda t: int(round(t))  # noqa: E731

        text_res = ":satellite: Ping Results :satellite:"
        self.logger.info("checking discord itself.")
        t1_dis = time.perf_counter()
        async with channel.typing():
            t2_dis = time.perf_counter()
            dis_ping = irnd((t2_dis - t1_dis) * 1000)
            self.logger.info("generating results....")
            self.logger.debug("generating discord res")
            text_res += f"\n{ping_emote(dis_ping)} Discord: `{dis_ping}ms`"

            self.logger.debug("generating websocket res")
            if ws_ping != float("nan"):
                ws_time = irnd(ws_ping * 1000)
                ws_res = f"{ping_emote(ws_time)} Websocket `{ws_time}ms`"
            else:
                ws_res = ":x: Websocket: `nan`"
            text_res += f"\n{ws_res}"
            await channel.send(content=text_res)


def setup(bot: PotiaBot):
    bot.add_cog(BotMetaCommands(bot))
