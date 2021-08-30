import logging

import discord
from discord.ext import commands
from phelper.bot import PotiaBot
from phelper.converters import TimeConverter
from phelper.timeparse import TimeString


class ChannelControl(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("ModTools.ChannelControl")

    async def _internal_lockdown_channel(self, channel: discord.TextChannel, lockdown: bool = True):
        all_overwrites = channel.overwrites

        is_failure = False
        for role, overwrite in all_overwrites.items():
            if role.name.lower() in ["@everyone", "bot", "muted"]:
                continue
            if "bot" in role.name.lower():
                continue
            if "muted" in role.name.lower():
                continue
            if not isinstance(overwrite, discord.PermissionOverwrite):
                continue
            if isinstance(lockdown, bool):
                overwrite.send_messages = not lockdown
            else:
                overwrite.send_messages = lockdown
            if lockdown:
                self.logger.info(f"Locking down channel {str(channel)} for role {role.name}")
            else:
                self.logger.info(f"Unlocking channel {str(channel)} for role {role.name}")
            try:
                await channel.set_permissions(role, overwrite=overwrite)
            except discord.Forbidden:
                is_failure = True
                self.logger.warning(f"Failed to lock down for role {role.name}, no sufficient permission!")
            except discord.HTTPException:
                is_failure = True
                self.logger.warning(f"Failed to lock down for role {role.name}, HTTP exception occured!")
        return is_failure

    @commands.command(aliases=["lock"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def lockdown(self, ctx: commands.Context, channel: commands.TextChannelConverter = None):
        """Lock down a channel"""
        if channel is None:
            channel: discord.TextChannel = ctx.channel
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("Ini bukanlah kanal teks!")

        is_failure = await self._internal_lockdown_channel(channel)

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
            channel: discord.TextChannel = ctx.channel
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("Ini bukanlah kanal teks!")

        is_failure = await self._internal_lockdown_channel(channel, None)

        if not is_failure:
            try:
                await channel.send("🔓 Kanal ini telah dibuka kembali!")
            except discord.Forbidden:
                self.logger.warning("Failed to sent information about channel unlocking, ignoring...")
                pass
            return
        await ctx.send(f"Kanal {channel.mention} gagal dibuka kembali!")

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    async def lockall(self, ctx: commands.Context):
        """Lock all channel"""
        channels = ctx.guild.text_channels
        all_failures = []
        ignored_category = [864004900383096832, 864044466107842581, 864004900383096833, 864069791404130314]
        for channel in channels:
            if channel.category_id is not None and channel.category_id in ignored_category:
                self.logger.warning("Channel is in ignored category...")
                continue
            is_failure = await self._internal_lockdown_channel(channel)
            if is_failure:
                all_failures.append(channel.mention)
                await ctx.send(f"⚠ {channel.mention} gagal dilockdown!")

        if len(all_failures) < 1:
            await ctx.send("🔐 Semua kanal teks telah dikunci!")
        else:
            message = "🔏 Kanal berikut gagal dikunci:\n- "
            message += "\n- ".join(all_failures)
            message += "\nMohon kunci dengan gunakan `p/lockdown` di tiap kanal!"
            await ctx.send(message)

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    async def unlockall(self, ctx: commands.Context):
        """Unlock all channels"""
        channels = ctx.guild.text_channels
        all_failures = []
        ignored_category = [864004900383096832, 864044466107842581, 864004900383096833, 864069791404130314]
        for channel in channels:
            if channel.category_id is not None and channel.category_id in ignored_category:
                self.logger.warning("Channel is in ignored category...")
                continue
            is_failure = await self._internal_lockdown_channel(channel, None)
            if is_failure:
                all_failures.append(channel.mention)
                await ctx.send(f"⚠ {channel.mention} gagal dibuka kembali!")

        if len(all_failures) < 1:
            await ctx.send("🔓 Semua kanal telah dibuka kembali!")
        else:
            message = "🔏 Kanal berikut gagal dibuka kembali:\n- "
            message += "\n- ".join(all_failures)
            message += "\nMohon kunci dengan gunakan `p/unlock` di tiap kanal!"
            await ctx.send(message)

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
            channel: discord.TextChannel = ctx.channel
        if not isinstance(channel, discord.TextChannel):
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
