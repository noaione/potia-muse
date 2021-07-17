import logging

import discord
from discord.ext import commands, tasks
from phelper.bot import PotiaBot


class UserWelcomer(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot

        self.logger = logging.getLogger("cogs.UserWelcomer")
        self._guild: discord.Guild = self.bot.get_guild(864004899783180308)

        self._rotating_presence_time.start()

    @commands.Cog.listener("on_member_join")
    async def _welcome_people(self, member: discord.Member):
        welcome_gate: discord.TextChannel = self._guild.get_channel(864063431399964693)


def setup(bot: PotiaBot):
    bot.add_cog(UserWelcomer(bot))
