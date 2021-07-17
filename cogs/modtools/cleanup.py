import logging

import discord
from discord.channel import TextChannel
from discord.ext import commands

from phelper.bot import PotiaBot
from phelper.utils import send_timed_msg


class MessageCleanup(commands.Cog):
    """
    A cog that cleans up messages in a channel.
    """

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

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def cleanuser(self, ctx: commands.Context, count: int, member: discord.Member):
        if count >= 100:
            return await ctx.send("Batas maksimal adalah 100 pesan")
        if count <= 0:
            return await ctx.send("Mohon berikan total pesan yang ingin dihapus")

        def delete_this(m: discord.Message):
            if m.author.id == member.id:
                return True
            return False

        kanal: TextChannel = ctx.channel
        deleted_message = await kanal.purge(limit=count, bulk=True, check=delete_this)
        await send_timed_msg(ctx, f"Berhasil menghapus {len(deleted_message)} pesan dari **{str(member)}**!")


def setup(bot: PotiaBot) -> None:
    bot.add_cog(MessageCleanup(bot))
