import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from math import ceil
from typing import Dict, List, MutableSet, Union

import discord
import wavelink
from discord.ext import commands
from phelper.bot import PotiaBot
from phelper.paginator import DiscordPaginatorUI
from wavelink.ext import spotify
from wavelink.tracks import SearchableTrack
from wavelink.utils import MISSING


class UnsupportedURLType(Exception):
    pass


def parse_playlist(data: dict):
    tracks = data["tracks"]
    return tracks


class YoutubeDirectLinkTrack(SearchableTrack):
    @classmethod
    async def search(
        cls, query: str, *, node: wavelink.Node = MISSING, return_first: bool = False
    ) -> Union[wavelink.Track, List[wavelink.Track]]:
        if node is MISSING:
            node = wavelink.NodePool.get_node()

        is_playlist = False
        if "/playlist" in query:
            is_playlist = True

        if is_playlist:
            playlists_data = []
            playlist_append = lambda x: playlists_data.extend(parse_playlist(x))  # noqa: E731
            await node.get_playlist(playlist_append, query)
            parsed_tracks = [cls(track["track"], track["info"]) for track in playlists_data]
            if return_first:
                return parsed_tracks[0]
            return parsed_tracks

        tracks = await node.get_tracks(cls, query)
        if return_first:
            return tracks[0]
        return tracks


class PotiaTrackRepeat(Enum):
    DISABLE = 0
    SINGLE = 1
    ALL = 2


def format_duration(duration: float):
    hours = duration // 3600
    duration = duration % 3600
    minutes = duration // 60
    seconds = duration % 60

    minutes = str(int(round(minutes))).zfill(2)
    seconds = str(int(round(seconds))).zfill(2)
    if hours >= 1:
        hours = str(int(round(hours))).zfill(2)
        return f"{hours}:{minutes}:{seconds}"
    return f"{minutes}:{seconds}"


@dataclass
class PotiaTrackQueued:
    track: wavelink.Track
    requester: discord.Member
    channel: discord.TextChannel


@dataclass
class PotiaMusikQueue:
    queue: asyncio.Queue[PotiaTrackQueued]
    repeat: PotiaTrackRepeat = PotiaTrackRepeat.DISABLE
    current: PotiaTrackQueued = None

    # Skipping stuff
    skip_votes: MutableSet[int] = field(default_factory=set)
    initiator: discord.Member = None


class PotiaMusik(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("Cog.PotiaMusik")

        self._PLAYER_QUEUE: Dict[int, PotiaMusikQueue] = {}
        bot.loop.create_task(self.setup_wavelink())

    async def setup_wavelink(self):
        """Connect to all nodes"""
        await self.bot.wait_until_ready()

        for node in self.bot.config.lavanodes:
            spotify_client = None
            if node.spotify:
                spotify_client = spotify.SpotifyClient(
                    client_id=node.spotify.id,
                    client_secret=node.spotify.secret,
                )
            await wavelink.NodePool.create_node(
                bot=self.bot,
                host=node.host,
                port=node.port,
                password=node.password,
                region=node.region,
                identifier=node.identifier,
                spotify_client=spotify_client,
            )

    def _create_queue(self, guild: discord.Guild):
        """Create a queue for a guild"""
        if guild.id not in self._PLAYER_QUEUE:
            self._PLAYER_QUEUE[guild.id] = PotiaMusikQueue(asyncio.Queue[PotiaTrackQueued]())

    async def _start_queue(self, guild: discord.Guild, track: PotiaTrackQueued):
        """Start a queue for a guild"""
        self._create_queue(guild)
        await self._PLAYER_QUEUE[guild.id].queue.put(track)

    def _get_queue(self, guild: discord.Guild):
        """Get the queue for a guild"""
        self._create_queue(guild)
        return self._PLAYER_QUEUE[guild.id]

    def _delete_queue(self, guild: discord.Guild):
        """Delete the queue for a guild"""
        if guild.id in self._PLAYER_QUEUE:
            del self._PLAYER_QUEUE[guild.id]

    def _reset_vote(self, guild: discord.Guild):
        """Reset the skip votes for a guild"""
        self._get_queue(guild).skip_votes.clear()

    def _set_current_track(self, guild: discord.Guild, track: PotiaTrackQueued):
        """Set the current track for a guild"""
        self._get_queue(guild).current = track

    def _flush_queue(self, guild: discord.Guild):
        """Flush the queue for a guild"""
        self._get_queue(guild).queue._queue.clear()  # Clear the internal queue

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Event fired when a node has finished connecting."""
        self.logger.info(f"Node: <{node.identifier}> [{node.region.name}] is ready!")

    @staticmethod
    async def _fetch_track_queue(queue: asyncio.Queue[PotiaTrackQueued]):
        """Fetch a track from the queue"""
        try:
            return await queue.get()
        except asyncio.CancelledError:
            return None

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track: wavelink.Track, reason: str):
        """Event fired when a track ends."""
        self.logger.info(f"Player: <{player.guild.id}> track has ended: {reason}")
        queue = self._get_queue(player.guild)
        self._set_current_track(player.guild, None)

        # Try to get new track
        try:
            self.logger.info("Trying to enqueue new track, waiting for 5 minutes...")
            new_track = await asyncio.wait_for(self._fetch_track_queue(queue.queue), timeout=300)
        except asyncio.TimeoutError:
            # No more tracks, stop the player
            self.logger.warning("No more track need to be loaded, disconnecting...")
            self._delete_queue(player.guild)
            await player.disconnect(force=True)
            return

        if new_track is None:
            self.logger.warning("Got cancellation flag for async, disconnecting...")
            self._delete_queue(player.guild)
            await player.disconnect(force=True)
            return

        self._reset_vote(player.guild)

        self.logger.info(f"Got new track for queue: {new_track.track}")
        await player.play(new_track.track)
        self._set_current_track(player.guild, new_track)
        embed = self._generate_track_embed(new_track.track, new_track.requester)
        await new_track.channel.send(embed=embed)

    def _generate_track_embed(self, track: wavelink.Track, author: discord.Member = None, position: int = -1):
        embed = discord.Embed(title="Now playing", colour=discord.Color.random())
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar)
        description = []
        # Judul: 【MV】ALKATRAZ- DEMONDICE
        description.append(f"**Judul**: {track.title}")
        # Artis: DEMONDICE
        if track.author:
            description.append(f"**Artis**: {track.author}")
        # Pemutar: N4O#8868
        if author:
            description.append(f"**Pemutar**: {author}")
        # Durasi: 04:37
        if position == -1:
            description.append(f"**Durasi**: {format_duration(track.duration)}")
        else:
            description.append(f"**Durasi**: {format_duration(position)}/{format_duration(track.duration)}")
        if isinstance(track, (wavelink.YouTubeTrack, YoutubeDirectLinkTrack)):
            embed.set_image(url=f"https://i.ytimg.com/vi/{track.identifier}/hqdefault.jpg")
            description.append(f"\n[Link](https://youtu.be/{track.identifier})")
        embed.description = "\n".join(description)
        return embed

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, player: wavelink.Player, track: wavelink.Track):
        """Event fired when a track starts playing."""
        self.logger.info(f"Track: <{track.title}> has started playing!")

    @commands.group(name="musik", aliases=["m", "music"])
    async def musik(self, ctx: commands.Context):
        pass

    @staticmethod
    async def search_track(query: str):
        """Search for a track"""
        if query.startswith("http"):
            if "spotify.com" in query:
                s_type = spotify.SpotifySearchType.track
                if "/playlist/" in query:
                    raise UnsupportedURLType
                if "/album/" in query:
                    s_type = spotify.SpotifySearchType.album
                results = await spotify.SpotifyTrack.search(
                    query,
                    type=s_type,
                    return_first="/album/" not in query,
                )
                return results, False
            elif "soundcloud" in query:
                raise UnsupportedURLType
            else:
                return_first = "/playlist" not in query
                results: YoutubeDirectLinkTrack = await YoutubeDirectLinkTrack.search(
                    query,
                    return_first=return_first,
                )
                return results, False

        results = await wavelink.YouTubeTrack.search(query, return_first=False)
        return results, True

    async def enqueue_single(self, ctx: commands.Context, track: wavelink.Track):
        """Enqueue a single track"""
        # Bind requester to track
        track_queue = PotiaTrackQueued(track, ctx.author, ctx.channel)
        await self._start_queue(ctx.guild, track_queue)
        queue = self._get_queue(ctx.guild)
        self.logger.info(f"Enqueueing: {track.title} by {track.author}")
        await ctx.send(
            f"Menambahkan `{track.title}` ke pemutar musik! (Posisi {queue.queue.qsize()})",
            reference=ctx.message,
        )

    async def select_track(self, ctx: commands.Context, all_tracks: List[wavelink.Track]):
        """Select a track"""

        messages = []
        messages.append("**Mohon ketik angka yang ingin anda tambahkan ke Bot!**")
        max_tracks = all_tracks[:7]
        for ix, track in enumerate(max_tracks, 1):
            messages.append(f"**{ix}**. `{track.title}` [{format_duration(track.duration)}]")

        await ctx.send("\n".join(messages), reference=ctx.message)

        def check(m: discord.Message):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.isdigit()
                and int(m.content) <= len(max_tracks)
            )

        res: discord.Message
        self.logger.info(f"Now waiting for {ctx.author} to select one of the tracks")
        try:
            res = await self.bot.wait_for("message", check=check, timeout=30.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            self.logger.warning("Message timeout, cancelling...")
            return None
        selected = max_tracks[int(res.content) - 1]
        self.logger.info(f"Selected track #{res.content} -- {selected}")
        return selected

    @musik.command(name="play", aliases=["setel", "mulai", "p"])
    async def musik_play(self, ctx: commands.Context, *, query: str):
        author: discord.Member = ctx.author

        if not ctx.voice_client:
            self.logger.info("VC is not instanted, connecting...")
            if author.voice is None:
                self.logger.error("VC is missing user.")
                return await ctx.send("Anda belum terhubung ke VC!", reference=ctx.message)
            vc: wavelink.Player = await author.voice.channel.connect(cls=wavelink.Player)
            self._create_queue(ctx.guild)
            guild = self._get_queue(ctx.guild)
            guild.initiator = author
            self._PLAYER_QUEUE[ctx.guild.id] = guild
        else:
            vc: wavelink.Player = ctx.voice_client

        self.logger.info(f"Trying to process: {query}")
        try:
            await ctx.send("Mencoba memuat lagu...", reference=ctx.message)
            all_results, should_pick = await self.search_track(query)
        except UnsupportedURLType:
            return await ctx.send("URL yang anda berikan tidak kami dukung!", reference=ctx.message)

        if not all_results:
            return await ctx.send("Tidak mendapatkan hasil yang cocok!", reference=ctx.message)

        if isinstance(all_results, list):
            if len(all_results) == 1:
                select_track = all_results[0]
                await self.enqueue_single(ctx, select_track)
            elif should_pick:
                select_track = await self.select_track(ctx, all_results)
                if select_track is None:
                    return await ctx.send(
                        "Timeout, mohon anda ulangi penambahan musik", reference=ctx.message
                    )
                await self.enqueue_single(ctx, select_track)
            else:
                # Queue all tracks
                self.logger.info("Playlist detected, loading tracks...")
                for track in all_results:
                    wrap_track = PotiaTrackQueued(track, author, ctx.channel)
                    await self._start_queue(ctx.guild, wrap_track)
                self.logger.info(f"Loaded {len(all_results)} tracks")

                await ctx.send(
                    content=f"Menambahkan playlist ke pemutar musik! Total ada: {len(all_results)} musik",
                )
        else:
            await self.enqueue_single(ctx, all_results)

        if not vc.is_playing():
            # Manually fire
            await self.on_wavelink_track_end(vc, None, "Initialized from p/musik play")

    @musik.command(name="join", aliases=["gabung"])
    async def musik_join(self, ctx: commands.Context):
        if ctx.voice_client:
            return await ctx.send("Bot telah join di VC lain, mohon putuskan terlebih dahulu!")

        author: discord.Member = ctx.author
        if author.voice is None:
            return await ctx.send("Anda belum join ke VC!", reference=ctx.message)
        self.logger.info(f"Joining VC: {author.voice.channel}")
        vc: wavelink.Player = await author.voice.channel.connect(cls=wavelink.Player)
        await ctx.message.add_reaction("👍")
        self.bot.dispatch("wavelink_track_end", vc, None, "Initialization from p/join")

    @musik.command(name="stop", aliases=["hentikan"])
    async def musik_stop(self, ctx: commands.Context):
        if not ctx.voice_client:
            return await ctx.send("Bot belum sama sekali join VC!")

        vc: wavelink.Player = ctx.voice_client
        # Flush the queue
        self._delete_queue(ctx.guild)
        self._create_queue(ctx.guild)

        await vc.stop()
        await ctx.message.add_reaction("👍")

    @musik.command(name="disconnect", aliases=["dc", "leave"])
    async def musik_dc(self, ctx: commands.Context):
        if not ctx.voice_client:
            return await ctx.send("Bot belum sama sekali join VC!")

        vc: wavelink.Player = ctx.voice_client
        self._delete_queue(ctx.guild)
        await vc.stop()
        await vc.disconnect(force=True)
        await ctx.message.add_reaction("👍")

    @musik.command(name="nowplaying", aliases=["np"])
    async def musik_nowplaying(self, ctx: commands.Context):
        if not ctx.voice_client:
            return await ctx.send("Bot belum sama sekali join VC!")

        queue = self._get_queue(ctx.guild)
        vc: wavelink.Player = ctx.voice_client
        if queue.current is None:
            return await ctx.send("Tidak ada lagu yang sedang disetel!")

        current_position = vc.position

        embed = self._generate_track_embed(
            queue.current.track, queue.current.requester, position=current_position
        )
        await ctx.send(embed=embed)

    def _check_perms(self, permission: discord.Permissions):
        if permission.administrator:
            return True
        if permission.manage_guild:
            return True
        if permission.manage_channels:
            return True
        return False

    def _get_requirement(self, vc: wavelink.Player):
        in_voice = vc.channel.members
        # 40% need to vote to skip.
        required = ceil(len(in_voice) * 0.4)
        return required

    @musik.command(name="skip", aliases=["lewat"])
    async def musik_skip(self, ctx: commands.Context):
        if not ctx.voice_client:
            return await ctx.send("Bot belum sama sekali join VC!")

        author: discord.Member = ctx.author

        vc: wavelink.Player = ctx.voice_client

        queue = self._get_queue(ctx.guild)
        if queue.queue.empty():
            return await ctx.send("Tidak ada lagu yang ada di daftar putar!")
        if queue.current is None:
            return await ctx.send("Tidak ada lagu yang berlangsung untuk di lewati!")
        if queue.initiator == author:
            await vc.stop()
            return await ctx.send("DJ utama melewati untuk lagu ini!")
        if self._check_perms(author.guild_permissions):
            await vc.stop()
            return await ctx.send("Seorang admin atau moderator melewati lagu ini!")
        if queue.current.requester == author:
            await vc.stop()
            return await ctx.send("Orang yang meminta lagu ini telah melewati lagu ini!")

        queue.skip_votes.add(author.id)

        # Do votes skip
        required = self._get_requirement(ctx.voice_client)
        if required >= len(queue.skip_votes):
            # Skip
            self.logger.info(f"Voted skip for song: {queue.current.track}")
            await vc.stop()
            await ctx.send(
                f"Lagu di skip dikarenakan {len(queue.skip_votes)} dari {required} orang vote untuk skip"
            )
        else:
            await ctx.send(
                f"Dibutuhkan {required} untuk nge-skip lagu ({len(queue.skip_votes)}/{required} orang)"
            )

    def _generate_simple_queue_embed(
        self, dataset: List[PotiaTrackQueued], current: int, maximum: int, real_total: int
    ):
        embed = discord.Embed(title=f"Daftar Putar ({current + 1}/{maximum})", colour=discord.Color.random())

        starting_track = ((current + 1) * 5) - 5

        description_fmt = []
        for n, track in enumerate(dataset, starting_track + 1):
            description_fmt.append(
                f"**{n}**. `{track.track.title}` [{format_duration(track.track.duration)}] (Diminta oleh: `{track.requester}`)"  # noqa: E501
            )

        embed.description = "\n".join(description_fmt)
        embed.set_footer(text=f"Tersisa {real_total} lagu")
        return embed

    @musik.group(name="queue", aliases=["q"])
    async def musik_queue(self, ctx: commands.Context):
        if not ctx.invoked_subcommand:
            if not ctx.voice_client:
                return await ctx.send("Bot belum sama sekali join VC!")

            queue = self._get_queue(ctx.guild)
            if queue.queue.empty():
                return await ctx.send("Tidak ada lagu yang akan disetel!")

            all_queued_tracks: List[wavelink.Track] = [d for d in queue.queue._queue]
            # Split the all_queued_tracks into chunks of 5
            chunked_tracks = [all_queued_tracks[i : i + 5] for i in range(0, len(all_queued_tracks), 5)]

            _partial_embed = partial(
                self._generate_simple_queue_embed,
                maximum=len(chunked_tracks),
                real_total=len(all_queued_tracks),
            )

            view = DiscordPaginatorUI(ctx, chunked_tracks)
            view.attach(_partial_embed)
            await view.interact()

    def _remove_track(self, guild: discord.Guild, queue: PotiaMusikQueue, position: int):
        try:
            del queue.queue._queue[position]
            self._PLAYER_QUEUE[guild.id] = queue
            return True
        except IndexError:
            return False

    @musik_queue.command(name="remove", aliases=["hapus"])
    async def musik_queue_delete(self, ctx: commands.Context, position: int):
        if not ctx.voice_client:
            return await ctx.send("Bot belum sama sekali join VC!")

        queue = self._get_queue(ctx.guild)
        if position < 1:
            return await ctx.send("Angka harus lebih dari satu!")

        if queue.queue.qsize() < 1:
            return await ctx.send("Tidak ada lagu di daftar putar!")

        if position > queue.queue.qsize():
            return await ctx.send("Angka tidak boleh lebih besar dari jumlah lagu di daftar putar!")
        elif position < 1:
            return await ctx.send("Angka harus lebih dari satu!")

        position -= 1
        track: PotiaTrackQueued = queue.queue._queue[position]
        if track.requester == ctx.author:
            success = self._remove_track(ctx.guild, queue, position)
        elif queue.initiator == ctx.author:
            success = self._remove_track(ctx.guild, queue, position)
        elif self._check_perms(ctx.author.guild_permissions):
            success = self._remove_track(ctx.guild, queue, position)
        else:
            return await ctx.send("Anda tidak memiliki hak untuk menghapus lagu tersebut dari daftar putar!")
        if success:
            await ctx.send(
                f"Lagu `{track.track.title}` berhasil dihapus dari daftar putar!", reference=ctx.message
            )
        else:
            await ctx.send("Lagu tidak dapat ditemukan di daftar putar!", reference=ctx.message)

    @musik_queue.command(name="clear", aliases=["bersihkan"])
    async def musik_queue_cleanup(self, ctx: commands.Context):
        if not ctx.voice_client:
            return await ctx.send("Bot belum sama sekali join VC!")

        author: discord.Member = ctx.author

        if self._check_perms(author.guild_permissions):
            self._flush_queue(ctx.guild)
            return await ctx.send("Daftar putar dibersihkan oleh Admin atau Moderator")

        queue = self._get_queue(ctx.guild)
        if queue.initiator == author:
            self._flush_queue(ctx.guild)
            return await ctx.send("Daftar putar dibersihkan oleh DJ utama!")

        await ctx.send(
            "Anda tidak memiliki hak untuk membersihkan daftar putar (Hanya Admin atau DJ pertama yang bisa)"
        )

    @musik.command(name="volume", aliases=["vol"])
    async def musik_volume(self, ctx: commands.Context, volume: int):
        if not ctx.voice_client:
            return await ctx.send("Bot belum sama sekali join VC!")

        if volume < 1 or volume > 100:
            return await ctx.send("Volume harus antara 1-100!")

        author = ctx.author
        queue = self._get_queue(ctx.guild)
        vc: wavelink.Player = ctx.voice_client
        if queue.initiator == author:
            await vc.set_volume(volume)
            return await ctx.send(f"Volume diubah menjadi {volume}%", reference=ctx.message)
        if self._check_perms(author.guild_permissions):
            await vc.volume(volume)
            return await ctx.send(f"Volume diubah menjadi {volume}%", reference=ctx.message)

        await ctx.send("Hanya DJ utama atau Admin yang dapat mengubah volume!")


def setup(bot: PotiaBot):
    bot.add_cog(PotiaMusik(bot))
