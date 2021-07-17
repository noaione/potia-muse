from datetime import datetime, timedelta, timezone
import logging

import discord
from discord.ext import commands, tasks
from phelper.bot import PotiaBot


class RollingPresence(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot

        self.logger = logging.getLogger("cogs.RollingPresence")
        self._wib_tz = timezone(timedelta(hours=7))
        self._previous_fmt = datetime.now(tz=self._wib_tz).strftime("%d/%m %H:%M WIB")
        self._is_run = False

        self._rotating_presence_time.start()

    def cog_unload(self):
        self._rotating_presence_time.cancel()

    @tasks.loop(seconds=1.0)
    async def _rotating_presence_time(self):
        if self._is_run:
            return
        self._is_run = True
        current_time = datetime.now(tz=self._wib_tz).strftime("%d/%m %H:%M WIB")
        if current_time != self._previous_fmt:
            self._previous_fmt = current_time
            try:
                await self.bot.modify_activity(current_time)
            except discord.HTTPException:
                self.logger.error(f"Failed to change the activity to {current_time}")
        self._is_run = False


def setup(bot: PotiaBot):
    bot.add_cog(RollingPresence(bot))
