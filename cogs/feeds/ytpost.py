import logging
from typing import List

import discord
from discord.ext import commands, tasks
from phelper.bot import PotiaBot


def trim_text(text: str, max_len: int) -> str:
    extra = " [...]"
    max_len -= 8
    if len(text) > max_len:
        return text[0:max_len] + extra
    return text


class FeedsYoutubePosts(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot

        self._museid_info = {
            "id": "UCxxnxya_32jcKj4yN1_kD7A",
            "name": "Muse Indonesia",
            "url": "https://www.youtube.com/channel/UCxxnxya_32jcKj4yN1_kD7A",
            "icon": "https://yt3.ggpht.com/a/AATXAJzBc6k_Wf5QCu4i0lpX7MksvS_f2R7vNTQ4Wub8=s900-c-k-c0xffffffff-no-rj-mo",  # noqa: E501
        }

        self.logger = logging.getLogger("Feeds.YouTubePosts")
        self._news_channels: discord.TextChannel = self.bot.get_channel(877899711946829905)
        self._youtube_posts.start()

    def cog_unload(self):
        self._youtube_posts.cancel()

    async def collect_muse_yt_posts(self):
        self.logger.info("Fetching community pages...")
        async with self.bot.aiosession.get(
            "https://naotimes-og.glitch.me/ytposts/UCxxnxya_32jcKj4yN1_kD7A"
        ) as resp:
            if resp.status != 200:
                self.logger.error("Got non 200 status code, returning anyway")
                return []
            content_type: str = resp.headers["content-type"]
            if not content_type.startswith("application/json"):
                self.logger.error("Received response are not JSON ignoring...")
                return []
            try:
                all_pages = await resp.json()
            except Exception:
                self.logger.error("Failed to parse JSON response")
                return []
        if not all_pages["success"]:
            self.logger.error("The API failed to parse the posts result")
            return []
        return all_pages["posts"]

    def _generate_embedded_posts(self, post_data: dict):
        post_id = post_data["id"]
        embed = discord.Embed(color=0xFF0000, url=f"https://www.youtube.com/post/{post_id}")
        embed.set_author(
            name="Muse Indonesia", url=self._museid_info["url"], icon_url=self._museid_info["icon"]
        )
        if post_data["content"]:
            embed.description = trim_text(post_data["content"], 1995)
        else:
            embed.description = "*Tidak ada teks*"
        if "thumbnail" in post_data and isinstance(post_data["thumbnail"], str):
            embed.set_image(url=post_data["thumbnail"])
        if "attachments" in post_data and isinstance(post_data["attachments"], list):
            for attach in post_data["attachments"]:
                tipe = attach["type"]
                data = attach["data"]
                if tipe == "video":
                    embed.add_field(name="Video", value=f"[{data}]({data})", inline=False)
                elif tipe == "poll":
                    poll_text = []
                    for poll in data:
                        poll_text.append(f"{poll['index'] + 1}. {poll['name']} ({poll['value']} voted)")
                    if len(poll_text) > 0:
                        embed.add_field(name="Poll", value="\n".join(poll_text), inline=False)
        return embed

    @tasks.loop(minutes=3.0)
    async def _youtube_posts(self):
        self._news_channels: discord.TextChannel = self.bot.get_channel(877899711946829905)
        try:
            self.logger.info("Starting _youtube_posts process...")
            collected_posts = await self.collect_muse_yt_posts()
            old_posts_data: List[str] = await self.bot.redis.get("potiamuse_ytposts", [])
            not_sended_yet = []
            for post in collected_posts:
                if post["id"] not in old_posts_data:
                    not_sended_yet.append(post)
            if len(not_sended_yet) < 1:
                self.logger.warning("Nothing to post, ignoring...")
                return
            self.logger.info(f"Will post {len(not_sended_yet)} posts")
            message_fmt = (
                "**Postingan baru di Laman Komunitas YouTube!**\nLink: <https://www.youtube.com/post/"
            )
            for post in not_sended_yet:
                try:
                    embed_post = self._generate_embedded_posts(post)
                    messages: discord.Message = await self._news_channels.send(
                        content=message_fmt + post["id"] + ">", embed=embed_post
                    )
                    old_posts_data.append(post["id"])
                except (discord.Forbidden, discord.HTTPException):
                    self.logger.warning(f"Failed to send this post: {post['id']}")
                    continue
                try:
                    await messages.publish()
                except (discord.Forbidden, discord.HTTPException):
                    self.logger.warning(f"Failed to publish post: {post['id']}, ignoring...")
            self.logger.info("Saving posted data to redis...")
            await self.bot.redis.set("potiamuse_ytposts", old_posts_data)
        except Exception as e:
            self.logger.error("Failed to run `_youtube_posts`, traceback and stuff:")
            self.bot.echo_error(e)

    @_youtube_posts.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()


def setup(bot: PotiaBot):
    bot.add_cog(FeedsYoutubePosts(bot))
