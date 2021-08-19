import logging
from typing import List

import discord
from discord.ext import commands, tasks
from phelper.bot import PotiaBot


class FeedsTwitterPosts(commands.Cog):
    ENDPOINT = "https://api.twitter.com/2/users/1385480130068246530/tweets"

    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot

        self.logger = logging.getLogger("Feeds.TwitterPosts")
        self._news_channels: discord.TextChannel = self.bot.get_channel(864043313166155797)
        self._twitter_posts.start()

    def cog_unload(self):
        self._twitter_posts.cancel()

    async def _fetch_twitter_posts(self):
        headers = {"Authorization": f"Bearer {self.bot.config.twitter_key}"}
        params = {
            "expansions": "author_id",
            "tweet.fields": "created_at",
        }
        async with self.bot.aiosession.get(self.ENDPOINT, params=params, headers=headers) as resp:
            data = await resp.json()
            return data.get("data")

    @tasks.loop(minutes=3.0)
    async def _twitter_posts(self):
        self._news_channels: discord.TextChannel = self.bot.get_channel(864043313166155797)
        try:
            self.logger.info("Starting _twitter_posts process...")
            collected_posts = await self._fetch_twitter_posts()
            old_posts_data: List[str] = await self.bot.redis.get("potiamuse_twposts", [])
            not_sended_yet = []
            for post in collected_posts:
                if post["id"] not in old_posts_data:
                    not_sended_yet.append(post["id"])

            message_fmt = "**Postingan baru di Twitter Muse Indonesia!**\n"
            message_fmt += "Tautan: https://twitter.com/muse_indonesia/status/{id}"
            for post in not_sended_yet:
                try:
                    messages: discord.Message = await self._news_channels.send(
                        content=message_fmt.format(id=post)
                    )
                    old_posts_data.append(post)
                except (discord.Forbidden, discord.HTTPException):
                    self.logger.warning(f"Failed to send this post: {post}")
                    continue
                try:
                    await messages.publish()
                except (discord.Forbidden, discord.HTTPException):
                    self.logger.warning(f"Failed to publish post: {post}, ignoring...")
            self.logger.info("Saving posted data to redis...")
            await self.bot.redis.set("potiamuse_twposts", old_posts_data)
        except Exception as e:
            self.logger.error("Failed to run `_twitter_posts`, traceback and stuff:")
            self.bot.echo_error(e)

    @_twitter_posts.before_loop
    async def before_twitter_posts(self):
        await self.bot.wait_until_ready()


def setup(bot: PotiaBot):
    bot.add_cog(FeedsTwitterPosts(bot))
