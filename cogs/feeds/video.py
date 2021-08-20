import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List

import discord
from discord.errors import HTTPException
from discord.ext import commands, tasks
from phelper.bot import PotiaBot

_MOCKED_SAMPLE = {
    "live": [
        {
            "id": "GRObk6TBtBw",
            "title": "I, Tsushima - Episode 08 [Takarir Indonesia]",
            "status": "upcoming",
            "startTime": 1629481800,
            "thumbnail": "https://i.ytimg.com/vi/GRObk6TBtBw/maxresdefault.jpg",
            "platform": "youtube",
            "channel": "UCxxnxya_32jcKj4yN1_kD7A",
        },
    ],
    "upcoming": [
        {
            "id": "GdPh2BFlBi8",
            "title": "Kupunya Dia dan Dirinya (Kanojo Mo Kanojo) - Episode 08 [Takarir Indonesia]",
            "status": "upcoming",
            "startTime": 1629483900,
            "thumbnail": "https://i.ytimg.com/vi/GdPh2BFlBi8/maxresdefault.jpg",
            "platform": "youtube",
            "channel": "UCxxnxya_32jcKj4yN1_kD7A",
        },
    ],
    "feeds": [],
}


class FeedsYoutubeVideo(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot

        self.logger = logging.getLogger("Feeds.YouTubeVideo")
        self._upcoming_message = 864062464509476874

        self._museid_info = {
            "id": "UCxxnxya_32jcKj4yN1_kD7A",
            "name": "Muse Indonesia",
            "url": "https://www.youtube.com/channel/UCxxnxya_32jcKj4yN1_kD7A",
            "icon": "https://yt3.ggpht.com/a/AATXAJzBc6k_Wf5QCu4i0lpX7MksvS_f2R7vNTQ4Wub8=s900-c-k-c0xffffffff-no-rj-mo",  # noqa: E501
        }

        self.wib: timezone = timezone(timedelta(hours=7))

        self._feeds_rgx = re.compile(
            r"(.*)http(?:s|)\:\/\/(?:www.|)youtube\.com\/watch\?(?P<params>.*)", re.IGNORECASE
        )

        self._last_data = 0
        self._mock_it = False

        self._upcoming_watcher.start()
        self._live_watcher.start()
        self._archive_feeds_watcher.start()

    def cog_unload(self):
        self._upcoming_watcher.cancel()
        self._live_watcher.cancel()
        self._archive_feeds_watcher.start()

    async def request_muse(self):
        if self._mock_it:
            return _MOCKED_SAMPLE["live"], _MOCKED_SAMPLE["upcoming"], _MOCKED_SAMPLE["feeds"]
        async with self.bot.aiosession.get("https://api.ihateani.me/museid/live") as resp:
            if "json" not in resp.content_type:
                raise ValueError()
            if resp.status != 200:
                raise ValueError()
            res = await resp.json()
            return res["live"], res["upcoming"], res["feeds"]

    async def request_feeds_data(self, limit=25):
        self.logger.info("Requesting feeds data...")
        _, _, feeds_data = await self.request_muse()
        if limit is not None:
            if isinstance(limit, str):
                try:
                    limit = int(limit)
                except ValueError:
                    limit = None
            if limit is not None:
                feeds_data = feeds_data[-limit:]  # skipcq: PYL-E1130
        return feeds_data

    async def update_upcoming(self):
        self.logger.info("Collecting upcoming data...")
        try:
            _, upcoming_yt, _ = await asyncio.wait_for(self.request_muse(), 20.0)
        except ValueError:
            self.logger.error("Received youtube data are not JSON, cancelling...")
            return ["Gagal mengambil data..."]
        except asyncio.TimeoutError:
            self.logger.error("Timeout error")
            return ["Gagal mengambil data..."]

        collected_yt: List[dict] = []
        for yt in upcoming_yt:
            start_time = yt["startTime"]
            if isinstance(start_time, str):
                start_time = int(start_time)
            if yt["platform"] != "youtube":
                continue
            lower_title = yt["title"].lower()
            if "freechat" in lower_title or "free chat" in lower_title:
                continue
            msg_design = ""
            msg_design += f"<t:{start_time}> "
            msg_design += f"- [{yt['title']}]"
            # https://youtu.be/nvTQ4TEPnsk
            msg_design += f"(https://youtu.be/{yt['id']})"
            collected_yt.append({"t": msg_design, "st": start_time})

        if collected_yt:
            collected_yt.sort(key=lambda x: x["st"])

        if not upcoming_yt:
            reparsed_collected_yt = ["Untuk sekarang, tidak ada!"]
            return reparsed_collected_yt

        reparsed_collected_yt = [m["t"] for m in collected_yt]
        reparsed_collected_yt.insert(0, "Waktu yang tertera merupakan waktu lokal anda!\n")
        return reparsed_collected_yt

    @staticmethod
    def _truncate_fields(dataset: list, limit: int = 1024):
        final_text = ""
        for data in dataset:
            add_text = data + "\n"
            length_now = len(final_text) + len(add_text)
            if length_now >= limit:
                break
            final_text += add_text
        return final_text

    @commands.command(name="toggleytmock")
    @commands.is_owner()
    async def _toggle_yt_mock(self, ctx: commands.Context):
        self._mock_it = not self._mock_it
        await ctx.send("Diubah!")

    @tasks.loop(minutes=5.0)
    async def _upcoming_watcher(self):
        if self._mock_it:
            return
        channels: discord.TextChannel = self.bot.get_channel(864018911884607508)
        try:
            self.logger.info("Running...")
            upcoming_res = await self.update_upcoming()
            embed = discord.Embed(timestamp=datetime.now(tz=self.wib))
            if upcoming_res:
                embed.add_field(name="Akan datang!", value=self._truncate_fields(upcoming_res), inline=False)
            else:
                embed.description = "Tidak ada anime yang akan tayang dalam waktu dekat!"
            embed.set_thumbnail(url=self._museid_info["icon"])
            embed.set_footer(text="Infobox v1.1 | Updated")
            self.logger.info("Updating messages...")
            partial_msg = channels.get_partial_message(self._upcoming_message)
            if partial_msg is not None:
                try:
                    await partial_msg.edit(embed=embed)
                except discord.HTTPException:
                    self.logger.error("Failed to update the upcoming embed!")
            self.logger.info("This run is now finished, sleeping for 5 minutes")
        except Exception as e:
            self.bot.echo_error(e)

    @tasks.loop(minutes=1.0)
    async def _live_watcher(self):
        channels: discord.TextChannel = self.bot.get_channel(864018911884607508)
        try:
            self.logger.info("Running...")
            current_lives_yt, _, _ = await self.request_muse()
            self.logger.info("Collecting all posted live message")
            old_posted_yt_lives: list = await self.bot.redis.get("potiamuse_live")
            self.logger.debug(f"Old live post: {old_posted_yt_lives}")

            self.logger.info("Propagating the IDs...")
            collected_posted_ids = [c["id"] for c in old_posted_yt_lives]
            self.logger.debug(f"Propagated posted IDs: {collected_posted_ids}")
            collected_lives_ids = [c["id"] for c in current_lives_yt]
            self.logger.debug(f"Propagated lives IDs: {collected_lives_ids}")

            self.logger.info("Collecting everything...")
            need_to_be_deleted = []
            need_to_be_posted = []
            for live_id in current_lives_yt:
                if live_id["id"] not in collected_posted_ids:
                    need_to_be_posted.append(live_id)
            for delete_id in old_posted_yt_lives:
                if delete_id["id"] not in collected_lives_ids:
                    need_to_be_deleted.append(delete_id)
            self.logger.debug(
                f"Propagated collection, posts: {need_to_be_deleted}, remove: {need_to_be_posted}"
            )
            self.logger.info("Deleting old data first...")
            for deletion in need_to_be_deleted:
                self.logger.info(f"Trying to delete: {deletion}")
                if self._mock_it:
                    continue
                if "takarir indonesia" in deletion["title"].lower():
                    self.bot.pevents.dispatch("remove live", deletion)
                try:
                    delete_this: discord.Message = await channels.fetch_message(deletion["msg_id"])
                    await delete_this.delete()
                except HTTPException:
                    self.logger.warning(f"Failed to remove video ID {deletion['id']}, ignoring...")

            collected_again = []
            self.logger.info("Now adding new data if exist...")
            for post_this in need_to_be_posted:
                self.logger.info(f"Posting: {post_this['id']}")
                if self._mock_it:
                    collected_again.append(post_this)
                    continue

                stream_url = f"https://youtube.com/watch?v={post_this['id']}"
                embed = discord.Embed(
                    title=post_this["title"],
                    colour=0xFF0000,
                    url=stream_url,
                    description=f"[Tonton Sekarang!]({stream_url})",
                )
                embed.set_image(
                    url=f"https://i.ytimg.com/vi/{post_this['id']}/maxresdefault.jpg"  # noqa: E501
                )
                embed.set_thumbnail(url="https://s.ytimg.com/yts/img/favicon_144-vfliLAfaB.png")
                embed.set_author(
                    name=self._museid_info["name"],
                    icon_url=self._museid_info["icon"],
                    url=self._museid_info["url"],
                )
                embed.set_footer(
                    text=post_this["id"], icon_url="https://s.ytimg.com/yts/img/favicon_144-vfliLAfaB.png"
                )
                try:
                    msg_info: discord.Message = await channels.send(content="Sedang Tayang!", embed=embed)
                    post_this["msg_id"] = msg_info.id
                    if "takarir indonesia" in post_this["title"].lower():
                        self.bot.pevents.dispatch("new live", post_this)
                    collected_again.append(post_this)
                except discord.HTTPException:
                    self.logger.warning(f"Failed to post video ID {post_this['id']}, ignoring...")

            self.logger.info("Merging with old video data...")
            old_posted_yt_lives.extend(collected_again)
            self.logger.info("Checking live status...")
            is_changed = False
            if len(collected_again) != self._last_data:
                channel_name = "🔴-rilisan-tayang"
                is_changed = True
            else:
                channel_name = "rilisan-tayang"

            self.logger.info("Saving data...")
            await self.bot.redis.set("potiamuse_live", collected_again)
            if is_changed and not self._mock_it:
                self.logger.info("Changing the channel name...")
                try:
                    await channels.edit(name=channel_name)
                except discord.HTTPException:
                    self.logger.warning("Failed to rename the channel name, ignoring...")
            self.logger.info("This run is now finished, sleeping for 1 minute")
        except Exception as e:
            self.bot.echo_error(e)

    @tasks.loop(minutes=2.0)
    async def _archive_feeds_watcher(self):
        if self._mock_it:
            return
        channels: discord.TextChannel = self.bot.get_channel(864018911884607508)
        try:
            self.logger.info("Running...")
            new_feeds = await self.request_feeds_data()
            if len(new_feeds) < 1:
                self.logger.warning("Got empty response from API, ignoring...")
                return
            saved_feeds = await self.bot.redis.get("potiamuse_feeds")
            first_run = False
            if saved_feeds is None:
                self.logger.info("First run detected, will not send anything and save everything!")
                first_run = True
                saved_feeds = []

            self.logger.info("Merging and filtering...")
            need_to_be_posted = list(filter(lambda x: x not in saved_feeds, new_feeds))

            concatted_feeds = []
            concatted_feeds.extend(saved_feeds)
            concatted_feeds.extend(need_to_be_posted)

            if first_run:
                need_to_be_posted = []

            self.logger.info("Saving and will start sending feed")
            await self.bot.redis.set("potiamuse_feeds", concatted_feeds)
            for post_this in need_to_be_posted:
                self.logger.info(f"Posting: {post_this}")
                text_fmt = f"Rilisan baru di Muse Indonesia! https://youtube.com/watch?v={post_this}"
                try:
                    msg_to_publish: discord.Message = await channels.send(content=text_fmt)
                    try:
                        await msg_to_publish.publish()
                    except HTTPException:
                        self.logger.warning(
                            f"Failed to publish video {post_this}, please publish it manually!"
                        )
                except HTTPException:
                    self.logger.warning(f"Failed to send video ID {post_this}, ignoring...")
            self.logger.info("This run is now finished, sleeping for 2 minutes")
        except Exception as e:
            self.bot.echo_error(e)

    @_upcoming_watcher.before_loop
    @_live_watcher.before_loop
    @_archive_feeds_watcher.before_loop
    async def _before_all_tasks(self):
        await self.bot.wait_until_ready()
        self.logger.info("All tasks are now ready")


def setup(bot: PotiaBot):
    bot.add_cog(FeedsYoutubeVideo(bot))
