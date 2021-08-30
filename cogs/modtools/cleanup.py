import logging

import discord
from discord.channel import TextChannel
from discord.ext import commands
from phelper.bot import PotiaBot
from phelper.timeparse import TimeString
from phelper.utils import send_timed_msg


class MessageCleanup(commands.Cog):
    """
    A cog that cleans up messages in a channel.
    """

    MAX_TIME = TimeString.parse("24h")

    def __init__(self, bot: PotiaBot) -> None:
        self.logger = logging.getLogger("ModTools.MessageCleanup")
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def clean(self, ctx: commands.Context, count: int = 50) -> None:
        """
        Cleans up messages in the current channel.

        This command will delete all messages that are older than 14 days.
        """
        if count >= 100:
            return await ctx.send("Batas maksimal adalah 100 pesan")
        if count <= 0:
            return await ctx.send("Mohon berikan total pesan yang ingin dihapus")
        kanal: TextChannel = ctx.channel
        deleted_message = await kanal.purge(limit=count, bulk=True)
        await send_timed_msg(ctx, f"Berhasil menghapus {len(deleted_message)} pesan!")

    @commands.command(name="cleanuser", aliases=["nukliruser"])
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    async def _modtools_nuke_user(
        self, ctx: commands.Context, user: commands.MemberConverter, time_limit: str = "24h"
    ):
        guild: discord.Guild = ctx.guild
        if not isinstance(user, discord.Member):
            return await ctx.send("Tidak dapat menemukan pengguna tersebut!")

        if user.guild != ctx.guild:
            return await ctx.send("User tersebut tidak ada di peladen ini!")

        maximum_deletion = TimeString.parse(time_limit)
        if maximum_deletion > self.MAX_TIME:
            return await ctx.send(f"{maximum_deletion} tidak dapat melebihi {self.MAX_TIME}!")

        bot_member = guild.get_member(self.bot.user.id)

        max_del_ts = maximum_deletion.to_delta()
        max_backward_time = self.bot.now() - max_del_ts
        confirm = await ctx.confirm(f"Apakah anda yakin akan menghapus {user} semua pesan dari?")
        if not confirm:
            return await ctx.send("*Dibatalkan*")

        init_msg = await ctx.send("Mulai proses menghapus pesan...")

        def _check_validate(m: discord.Message):
            return m.author == user and init_msg.id != m.id

        all_channels = guild.text_channels
        all_deleted = 0
        for kanal in all_channels:
            self.logger.info(f"Trying to delete message by user `{user}` in `{kanal}`")
            permission: discord.Permissions = kanal.permissions_for(bot_member)
            if not permission.manage_messages:
                continue
            deleted = await kanal.purge(limit=None, check=_check_validate, after=max_backward_time)
            count = len(deleted)
            await init_msg.edit(f"Berhasil menghapus {count:,} pesan dari kanal #{kanal.name}")
            all_deleted += len(count)

        await init_msg.edit(f"Berhasil menghapus {all_deleted:,} pesan dari semua kanal!")


def setup(bot: PotiaBot) -> None:
    bot.add_cog(MessageCleanup(bot))
