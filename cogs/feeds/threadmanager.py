import logging

import discord
from discord.enums import ChannelType
from discord.ext import commands
from phelper.bot import PotiaBot


class FeedsThreadManager(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("Feeds.ThreadManager")
        self._TEMPLATE = "🔴 | {title} | {id}"
        self._MSG_TEMPLATE = (
            "Thread ini akan digunakan untuk membicarakan `{title}`\nhttps://youtube.com/watch?v={id}"
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

    @staticmethod
    def _remove_takarir(title: str):
        return title.replace("[Takarir Indonesia]", "").rstrip()

    def _cleanup_title(self, id: str, title: str):
        id_len = len(id)
        first_part = "🔴 | "
        second_part = " | "
        additional = " [...]"
        title = self._remove_takarir(title)
        MAX_LEN = 100
        if len(title) + id_len + len(first_part) + len(second_part) > MAX_LEN:
            total_cut = id_len + len(first_part) + len(second_part) + len(additional)
            title = title[: MAX_LEN - total_cut] + additional
        return title

    async def _on_new_live_creation(self, data: dict):
        self.logger.info("Received event for live thread creation.")
        channel: discord.TextChannel = self.bot.get_channel(864019283490242570)
        live_id = data["id"]
        title = data["title"]
        self.logger.info("Checking if live thread exists...")
        exist = await self.bot.redis.get(f"potia_livethread_{live_id}")
        if exist is not None:
            self.logger.warning("Live thread already exist!")
            return

        self.logger.info("Live thread does not exist, creating...")
        new_thread = await channel.create_thread(
            name=self._TEMPLATE.format(id=live_id, title=self._cleanup_title(live_id, title)),
            type=ChannelType.public_thread,
            reason=f"Auto creation for live thread: {live_id}",
        )
        self.logger.info("Sending sample message...")
        message = await new_thread.send(
            content=self._MSG_TEMPLATE.format(id=live_id, title=self._remove_takarir(title))
        )
        self.logger.info("Saving to redis state!")
        await self.bot.redis.set(f"potia_livethread_{live_id}", new_thread.id)
        try:
            await message.pin()
        except discord.Forbidden:
            pass

    async def _on_old_live_archival(self, data: dict):
        self.logger.info("Received event for live thread deletion/archival!")
        channel: discord.TextChannel = self.bot.get_channel(864019283490242570)
        live_id = data["id"]
        self.logger.info("Checking if live thread exists...")
        exist = await self.bot.redis.get(f"potia_livethread_{live_id}")
        if exist is None:
            self.logger.warning("Live thread does not exist!")
            return

        self.logger.info("Live thread exists, archiving...")
        the_thread = channel.get_thread(exist)
        if the_thread is None:
            self.logger.warning("Live thread does not exist!")
            return
        await the_thread.edit(archived=True, locked=True)
        await self.bot.redis.delete(f"potia_livethread_{live_id}")


def setup(bot: PotiaBot):
    bot.add_cog(FeedsThreadManager(bot))
