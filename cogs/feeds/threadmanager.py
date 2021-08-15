import discord
import logging
from discord.enums import ChannelType
from discord.ext import commands

from phelper.bot import PotiaBot


class FeedsThreadManager(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("Feeds.ThreadManager")
        self._guild: discord.Guild = self.bot.get_guild(864004899783180308)
        self._channel: discord.TextChannel = self._guild.get_channel(864019381230501898)
        self._TEMPLATE = "🔴 | {title} | {id}"
        self._MSG_TEMPLATE = (
            "Thread ini akan digunakan untuk membicarakan `{title}` dengan\nhttps://youtube.com/watch?v={id}"
        )

        self._EVENTS = {
            "new live": self._on_new_live_creation,
            "remove live": self._on_old_live_archival,
        }
        for event, callback in self._EVENTS.items():
            self.bot.pevents.on(event, callback)

    def cog_unload(self):
        for event in self._EVENTS.keys():
            self.bot.pevents.off(event)

    async def _on_new_live_creation(self, data: dict):
        live_id = data["id"]
        title = data["title"]
        self.logger.info("Checking if live thread exists...")
        exist = await self.bot.redis.get(f"potia_livethread_{live_id}")
        if exist is not None:
            self.logger.warning("Live thread already exist!")
            return

        self.logger.info("Live thread does not exist, creating...")
        new_thread = await self._channel.start_thread(
            name=self._TEMPLATE.format(id=live_id, title=title),
            type=ChannelType.public_thread,
            reason="Live thread",
        )
        await new_thread.send(content=self._MSG_TEMPLATE.format(id=live_id, title=title))
        await self.bot.redis.set(f"potia_livethread_{live_id}", new_thread.id)

    async def _on_old_live_archival(self, data: dict):
        live_id = data["id"]
        self.logger.info("Checking if live thread exists...")
        exist = await self.bot.redis.get(f"potia_livethread_{live_id}")
        if exist is None:
            self.logger.warning("Live thread does not exist!")
            return

        self.logger.info("Live thread exists, archiving...")
        the_thread = self._channel.get_thread(exist)
        if the_thread is None:
            self.logger.warning("Live thread does not exist!")
            return
        await the_thread.edit(archived=True, locked=True)
        await self.bot.redis.delete(f"potia_livethread_{live_id}")
