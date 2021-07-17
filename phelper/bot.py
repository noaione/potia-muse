import logging

import discord
from phelper.puppeeter import PuppeeterGenerator
import traceback
from typing import Dict, Union

from discord.ext import commands

from .redis import RedisBridge
from .utils import __version__


class PotiaBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.bot_id: str
        self.bot_token: str

        self.logger = logging.getLogger("PotiaBot")

        self.semver: str = __version__
        self.bot_config: Dict[str, Union[str, int, bool, Dict[str, Union[str, int, bool]]]]
        self.prefix: str

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
