import functools
import logging
import os
import sys
import traceback
from contextlib import suppress
from datetime import datetime, timezone
from typing import AnyStr, TypeVar, Union

import aiohttp
import discord
from discord.ext import commands

from .config import PotiaBotConfig
from .events import EventManager
from .modlog import PotiaModLog
from .puppeeter import PuppeeterGenerator
from .redis import RedisBridge
from .utils import __version__, explode_filepath_into_pieces, prefixes_with_data
from .welcomer import WelcomeGenerator

T = TypeVar("T")
UserContext = Union[discord.Member, discord.User, discord.TeamMember]
ContextModlog = Union[discord.Message, discord.Member, discord.Guild]


class StartupError(Exception):
    def __init__(self, base: Exception) -> None:
        super().__init__()
        self.exception = base


class PotiaBot(commands.Bot):
    def __init__(self, base_path: str, bot_config: PotiaBotConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("PotiaBot")
        self.semver = __version__
        self.config = bot_config
        self.prefix = bot_config.default_prefix
        self.fcwd = base_path

        self._modlog_channel: discord.TextChannel = None
        self.redis: RedisBridge = None
        self.puppet: PuppeeterGenerator = None
        self.pevents: EventManager = None
        self.aiosession: aiohttp.ClientSession = None

    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    def echo_error(self, error: Exception):
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        self.logger.error("Exception occured\n" + "".join(tb))

    @staticmethod
    def is_mentionable(ctx: commands.Context, user: UserContext) -> str:
        """Check if the user is mentionable
        :param ctx: The context
        :type ctx: commands.Context
        :param user: The user
        :type user: UserContext
        :return: Formatted mention or just user#discriminator
        :rtype: str
        """
        member = ctx.message.guild.get_member(user.id)
        if member is None:
            return str(user)
        return user.mention

    async def initialize(self):
        """|coro|

        Initialize the main bot process
        """
        self.logger.info("Initializing bot...")
        self.logger.info("Connecting to RedisDB....")

        redis_conf = self.config.redis
        redis_conn = RedisBridge(redis_conf.ip_hostname, redis_conf.port, redis_conf.password, self.loop)
        try:
            await redis_conn.connect()
        except ConnectionRefusedError as ce:
            self.logger.error("Failed to connect to RedisDB, aborting...")
            raise StartupError(ce)
        self.redis = redis_conn

        self.logger.info("Fetching prefixes data...")
        srv_prefixes = await redis_conn.getalldict("potiapre_*")
        fmt_prefixes = {}
        for srv, pre in srv_prefixes.items():
            fmt_prefixes[srv[9:]] = pre

        self.logger.info("Preparing puppeeter")
        puppet_gen = PuppeeterGenerator(self.loop)
        await puppet_gen.init()
        await puppet_gen.bind(WelcomeGenerator)
        self.puppet = puppet_gen
        prefixes = functools.partial(prefixes_with_data, prefixes_data=fmt_prefixes, default=self.prefix)
        self.command_prefix = prefixes

    async def login(self, *args, **kwargs):
        """Logs in the the bot into Discord."""
        self.aiosession = aiohttp.ClientSession(
            headers={"User-Agent": f"PotiaBot/v{self.semver} (https://github.com/noaione/potia-muse)"}
        )

        await self.initialize()
        await super().login(*args, **kwargs)
        self.load_extensions()

    async def close(self):
        """Close discord connection and all other stuff that I opened!"""
        for ext in list(self.extensions):
            with suppress(Exception):
                self.unload_extension(ext)

        for cog in list(self.cogs):
            with suppress(Exception):
                self.remove_cog(cog)

        await super().close()
        if self.pevents:
            self.logger.info("Closing event manager...")
            await self.pevents.close()
        if self.puppet:
            self.logger.info("Closing puppeteer")
            await self.puppet.close()

        if self.aiosession:
            self.logger.info("Closing aiohttp Session...")
            await self.aiosession.close()

        if self.redis:
            self.logger.info("Shutting down redis connection...")
            await self.redis.close()

    async def on_ready(self):
        """|coro|

        Called when the bot is ready!
        """
        self.logger.info("---------------------------------------------------------------")
        self.logger.info("Bot has now established connection with Discord!")
        await self.modify_activity("🥐 | @author N4O")
        self.logger.info("Binding modlog...")
        modlog_channel = self.get_channel(self.config.modlog_channel)
        if isinstance(modlog_channel, discord.TextChannel):
            self.set_modlog(modlog_channel)
            self.logger.info(f"Modlog binded to: #{modlog_channel.name} ({modlog_channel.id})")
        else:
            self.logger.warning("Modlog channel is not a text channel, disabling modlog")
        self.logger.info("---------------------------------------------------------------")
        self.logger.info("Bot Ready!")
        self.logger.info("Using Python {}".format(sys.version))
        self.logger.info("And Using Discord.py v{}".format(discord.__version__))
        self.logger.info("---------------------------------------------------------------")
        self.logger.info("Bot Info:")
        self.logger.info("Username: {}".format(self.user.name))
        self.logger.info("Client ID: {}".format(self.user.id))
        self.logger.info("Running PotiaBot version: {}".format(__version__))
        self.logger.info("---------------------------------------------------------------")

    def available_extensions(self):
        """Returns all available extensions"""
        ALL_EXTENSION_LIST = []
        IGNORED = ["__init__", "__main__"]
        current_path = self.fcwd.replace("\\", "/")
        for (dirpath, _, filenames) in os.walk(os.path.join(self.fcwd, "cogs")):
            for filename in filenames:
                if filename.endswith(".py"):
                    dirpath = dirpath.replace("\\", "/")
                    dirpath = dirpath.replace(current_path, "")
                    if dirpath.startswith("./"):
                        dirpath = dirpath[2:]
                    dirpath = dirpath.lstrip("/")
                    expanded_path = ".".join(explode_filepath_into_pieces(dirpath))
                    just_the_name = filename.replace(".py", "")
                    if just_the_name in IGNORED:
                        continue
                    ALL_EXTENSION_LIST.append(f"{expanded_path}.{just_the_name}")
        ALL_EXTENSION_LIST.sort()
        return ALL_EXTENSION_LIST

    def load_extensions(self):
        """Load all extensions"""
        ALL_EXTENSIONS = self.available_extensions()

        for extension in ALL_EXTENSIONS:
            if extension in self.config.init_config.cogs_skip:
                self.logger.info(f"Skipping {extension}...")
                continue
            try:
                self.load_extension(extension)
            except commands.ExtensionError as enoff:
                self.logger.error(f"Failed to load {extension}")
                self.echo_error(enoff)

    def load_extension(self, name: str, *, package: T.Optional[str] = None):
        self.logger.info(f"Loading module: {name}")
        super().load_extension(name, package=package)
        self.logger.info(f"{name} module is now loaded!")

    def unload_extension(self, name: str):
        self.logger.info(f"Unloading module: {name}")
        super().unload_extension(name)
        self.logger.info(f"{name} module is now unloaded!")

    async def modify_activity(self, message: str):
        activity = discord.Game(name=f"{message} | p/info")
        await self.change_presence(activity=activity)

    def set_modlog(self, channel: discord.TextChannel):
        self._modlog_channel = channel

    # Modlog feature

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

    # Helper
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
