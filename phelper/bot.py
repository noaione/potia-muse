import logging
import traceback
from datetime import datetime, timezone
from typing import AnyStr, Dict, Union

import aiohttp
import discord
from discord.ext import commands

from .modlog import PotiaModLog
from .puppeeter import PuppeeterGenerator
from .redis import RedisBridge
from .utils import __version__

ContextModlog = Union[discord.Message, discord.Member, discord.Guild]


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

    def should_modlog(
        self,
        context: ContextModlog,
        user_data: Union[discord.Member, discord.User] = None,
        include_bot: bool = False,
    ):
        """Check if the listener can continue and log to modlog.

        :param context: The context
        :type context: ContextModlog
        :param include_bot: Should we include bot stuff or not, defaults to False
        :type include_bot: bool, optional
        """
        if context is None:
            return False
        server_data = context
        if not isinstance(context, discord.Guild):
            server_data = context.guild
        guild_info: discord.Guild = None
        if self._modlog_channel is not None:
            guild_info = self._modlog_channel.guild

        if guild_info is not None and guild_info.id != server_data.id:
            return False
        if user_data is not None and user_data.bot and not include_bot:
            return False
        return True

    async def send_modlog(self, modlog: PotiaModLog):
        if self._modlog_channel is None:
            return
        if modlog.embed is not None:
            embed = modlog.embed
            if modlog.timestamp is None:
                modlog.timestamp = None
            if embed.colour == discord.Embed.Empty:
                embed.colour = discord.Color.random()
            if embed.timestamp == discord.Embed.Empty:
                embed.timestamp = datetime.fromtimestamp(modlog.timestamp, tz=timezone.utc)
            modlog.embed = embed

        # TODO: create more sophisicated method later
        real_message = modlog.message
        if not real_message:
            real_message = None
        self.logger.info(f"Content: {real_message}, embed: {modlog.embed}")
        await self._modlog_channel.send(content=real_message, embed=modlog.embed)

    async def upload_ihateanime(self, content: AnyStr, filename: str = None):
        timestamp = int(round(self.now().timestamp()))
        if filename is None:
            filename = f"PotiaBot.{timestamp}.txt"
        else:
            if not filename.endswith(".txt"):
                filename += ".txt"
        if not isinstance(content, bytes):
            content = content.encode("utf-8")
        async with aiohttp.ClientSession() as session:
            form_data = aiohttp.FormData()
            form_data.add_field(
                name="file",
                value=content,
                content_type="text/plain",
                filename=filename,
            )
            try:
                async with session.post("https://p.ihateani.me/upload", data=form_data) as resp:
                    if resp.status == 200:
                        res = await resp.text()
                        return res
            except aiohttp.ClientError:
                return None
        return None
