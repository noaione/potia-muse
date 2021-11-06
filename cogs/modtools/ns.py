import asyncio
from dataclasses import dataclass
from typing import Dict, List

import discord
from discord.ext import commands, tasks
from phelper.bot import PotiaBot


@dataclass
class Detected:
    u: discord.Member
    t: int
    c: int = 1

    def i(self):
        self.c += 1

    def ud(self, ts: int):
        self.t = ts
        self.i()


class NSCog(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self._h: Dict[int, Detected] = {}

        self._L = asyncio.Lock()
        self._repeater.start()

    def cog_unload(self):
        self._repeater.cancel()

    async def _report(self, u: discord.Member, c: int):
        d = self.bot.get_channel(864044546361786388)
        if d is None:
            return

        embed = discord.Embed(title="💳 Nitro Scam", color=discord.Color.dark_red(), timestamp=self.bot.now())
        desc = [f"**User**: {u.mention} ({u.id})", f"**Total pesan**: {c} pesan"]
        embed.description = "\n".join(desc)
        embed.set_thumbnail(url=u.avatar)
        embed.set_footer(text="💳 Nitro Scam")
        await d.send(embed=embed)

    @tasks.loop(seconds=10)
    async def _repeater(self):
        c = self.bot.now().timestamp()
        async with self._L:
            dt: List[int] = []
            for v in self._h.copy().values():
                # Give period of 1 mins before reporting.
                if v.t + 60 < c:
                    self.bot.loop.create_task(
                        self._report(v.u, v.c), name=f"poggers-repeat-ns-{v.t}_{v.u.id}"
                    )
                    dt.append(v.u.id)
            for m in dt:
                self._h.pop(m)

    @_repeater.before_loop
    async def _before_repeater(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener("on_message")
    async def _detect(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is None:
            return

        cmsg = message.clean_content.lower()
        if "@everyone" in cmsg and "nitro" in cmsg:
            if message.author.id not in self._h:
                self._h[message.author.id] = Detected(message.author, message.created_at.timestamp())
            else:
                self._h[message.author.id].ud(message.created_at.timestamp())

            try:
                await message.delete()
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                pass


def setup(bot: PotiaBot):
    bot.add_cog(NSCog(bot))
