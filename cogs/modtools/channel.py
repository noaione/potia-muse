import logging

import discord
from discord.channel import TextChannel
from discord.ext import commands
from phelper.bot import PotiaBot
from phelper.timeparse import TimeConverter, TimeString


class ChannelControl(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("ModTools.ChannelControl")

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def lockdown(self, ctx: commands.Context, channel: commands.TextChannelConverter = None):
        """Lock down a channel"""
        if channel is None:
            channel: TextChannel = ctx.channel
        if not isinstance(channel, TextChannel):
            return await ctx.send("Ini bukanlah kanal teks!")

        all_overwrites = channel.overwrites

        is_failure = False
        for role, overwrite in all_overwrites.items():
            if role.name.lower() in ["@everyone", "bot"]:
                continue
            if not isinstance(overwrite, discord.PermissionOverwrite):
                continue
            overwrite.send_messages = False
            self.logger.info(f"Locking down for role {role.name}")
            try:
                await channel.set_permissions(role, overwrite=overwrite)
            except discord.Forbidden:
                is_failure = True
                self.logger.warning(f"Failed to lock down for role {role.name}, no sufficient permission!")
            except discord.HTTPException:
                is_failure = True
                self.logger.warning(f"Failed to lock down for role {role.name}, HTTP exception occured!")

        if not is_failure:
            try:
                await channel.send("🔐 Kanal ini telah dikunci!")
            except discord.Forbidden:
                self.logger.warning("Failed to sent information about channel lockdown, ignoring...")
                pass
            return
        await ctx.send(f"Kanal {channel.mention} gagal dilockdown!")

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context, channel: commands.TextChannelConverter = None):
        """Unlock a channel"""
        if channel is None:
            channel: TextChannel = ctx.channel
        if not isinstance(channel, TextChannel):
            return await ctx.send("Ini bukanlah kanal teks!")

        all_overwrites = channel.overwrites

        is_failure = False
        for role, overwrite in all_overwrites.items():
            if role.name.lower() in ["@everyone", "bot"]:
                continue
            if not isinstance(overwrite, discord.PermissionOverwrite):
                continue
            overwrite.send_messages = True
            self.logger.info(f"Locking down for role {role.name}")
            try:
                await channel.set_permissions(role, overwrite=overwrite)
            except discord.Forbidden:
                is_failure = True
                self.logger.warning(f"Failed to unlock for role {role.name}, no sufficient permission!")
            except discord.HTTPException:
                is_failure = True
                self.logger.warning(f"Failed to unlock for role {role.name}, HTTP exception occured!")

        if not is_failure:
            try:
                await channel.send("🔓 Kanal ini telah dibuka kembali!")
            except discord.Forbidden:
                self.logger.warning("Failed to sent information about channel unlocking, ignoring...")
                pass
            return
        await ctx.send(f"Kanal {channel.mention} gagal dibuka kembali!")

    @commands.command()
    @commands.has_guild_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def slowmode(
        self,
        ctx: commands.Context,
        amount: TimeConverter = "0",
        channel: commands.TextChannelConverter = None,
    ):
        """Set slowmode on a channel"""
        if channel is None:
            channel: TextChannel = ctx.channel
        if not isinstance(channel, TextChannel):
            return await ctx.send("Ini bukanlah kanal teks!")

        total_seconds = 0
        if isinstance(amount, TimeString):
            total_seconds = amount.timestamp()

        if channel.slowmode_delay == total_seconds:
            if ctx.channel.id != channel.id:
                return await ctx.send(f"⚙ Slowmode kanal <#{channel.mention}> tidak berubah.")
            return await ctx.send("⚙ Slowmode tidak berubah.")

        # 6 hours
        SLOWMODE_SECONDS_MAXIMUM = 6 * 60 * 60
        if total_seconds < 0:
            return await ctx.send("⚙⚠ Waktu slowmode harus lebih dari sama dengan 0 detik!")
        if total_seconds > SLOWMODE_SECONDS_MAXIMUM:
            return await ctx.send("⚙⚠ Waktu slowmode tidak bisa lebih dari 6 jam!")

        slowmode_text = "dinonaktifkan!"
        if total_seconds > 0:
            slowmode_text = f"diubah menjadi {total_seconds} detik!"

        try:
            await channel.edit(slowmode_delay=total_seconds)
            if ctx.channel.id != channel.id:
                return await ctx.send(f"⚙ Slowmode kanal <#{channel.mention}> {slowmode_text}")
            await ctx.send(f"⚙ Slowmode {slowmode_text}")
        except discord.Forbidden:
            if ctx.channel.id != channel.id:
                return await ctx.send(f"⚙⚠ Gagal mengubah slowmode di kanal <#{channel.mention}>")
            await ctx.send("⚙⚠ Gagal merubah slowmode!")


def setup(bot: PotiaBot):
    bot.add_cog(ChannelControl(bot))
