from datetime import datetime, timezone
import logging
import traceback
from typing import Dict, Union

import discord
from discord.ext import commands

from .modlog import PotiaModLog
from .puppeeter import PuppeeterGenerator
from .redis import RedisBridge
from .utils import __version__

SendContext = Union[discord.TextChannel, commands.Context]


class PotiaBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.bot_id: str
        self.bot_token: str

        self.logger = logging.getLogger("PotiaBot")

        self.semver: str = __version__
        self.bot_config: Dict[str, Union[str, int, bool, Dict[str, Union[str, int, bool]]]]
        self.prefix: str
        self._modlog_channel: discord.TextChannel = None

        self.fcwd: str
        self.redis: RedisBridge = None
        self.puppet: PuppeeterGenerator = None

    def echo_error(self, error):
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        self.logger.error("Exception occured\n" + "".join(tb))

    @staticmethod
    def is_mentionable(ctx, user_data):
        member = ctx.message.guild.get_member(user_data.id)
        if member is None:
            return f"{user_data.name}#{user_data.discriminator}"
        return f"<@{user_data.id}>"

    async def modify_activity(self, message: str):
        activity = discord.Game(name=f"{message} | p/info")
        await self.change_presence(activity=activity)

    def set_modlog(self, channel: discord.TextChannel):
        self._modlog_channel = channel

    def now(self):
        return datetime.now(tz=timezone.utc)

    async def send_modlog(self, modlog: PotiaModLog):
        if self._modlog_channel is None:
            return
        if modlog.embed is not None:
            embed = modlog.embed
            if modlog.timestamp is None:
                modlog.set_timestamp()
            embed.colour = discord.Color.random()
            embed.timestamp = datetime.fromtimestamp(modlog.timestamp, tz=timezone.utc)

        # TODO: create more sophisicated method later
        await self._modlog_channel.send(content=modlog.message, embed=modlog.embed)
