import logging
from datetime import datetime
from typing import Union

import discord
from discord.ext import commands
from phelper.bot import PotiaBot
from phelper.modlog import PotiaModLog, PotiaModLogAction
from phelper.utils import rounding


class LoggingMember(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("log.LoggingMember")

    @staticmethod
    def strftime(dt_time: datetime) -> str:
        month_en = dt_time.strftime("%B")
        tl_map = {
            "January": "Januari",
            "February": "Februari",
            "March": "Maret",
            "April": "April",
            "May": "Mei",
            "June": "Juni",
            "July": "Juli",
            "August": "Agustus",
            "September": "September",
            "October": "Oktober",
            "November": "November",
            "December": "Desember",
        }
        month_id = tl_map.get(month_en, month_en)
        final_data = dt_time.strftime("%d ") + month_id
        final_data += dt_time.strftime(" %Y, %H:%M:%S UTC")
        return final_data

    def _generate_log(self, action: PotiaModLogAction, data: dict):
        user_data: discord.Member = data["user_data"]
        desc_data = []
        current_time = self.bot.now()
        desc_data.append(f"**• Pengguna**: {user_data.name}#{user_data.discriminator}")
        desc_data.append(f"**• ID Pengguna**: {user_data.id}")
        desc_data.append(f"**• Akun Bot?**: {'Ya' if user_data.bot else 'Tidak'}")
        desc_data.append(f"**• Akun Dibuat**: {self.strftime(user_data.created_at)}")
        desc_data.append(f"**• Terjadi pada**: <t:{rounding(current_time.timestamp())}>")
        author_data = {
            "name": f"{user_data.name}#{user_data.discriminator}",
            "icon_url": str(user_data.display_avatar),
        }
        modlog = PotiaModLog(action=action, timestamp=current_time.timestamp())
        if action == PotiaModLogAction.MEMBER_JOIN:
            embed = discord.Embed(title="📥 Anggota Bergabung", color=0x83D66B, timestamp=current_time)
            embed.description = "\n".join(desc_data)
            embed.set_footer(text="🚪 Bergabung")
            embed.set_author(**author_data)
            embed.set_thumbnail(url=str(user_data.display_avatar))
            modlog.embed = embed
        elif action == PotiaModLogAction.MEMBER_LEAVE:
            embed = discord.Embed(title="📥 Anggota Keluar", color=0xD66B6B, timestamp=current_time)
            embed.description = "\n".join(desc_data)
            embed.set_footer(text="🚪 Keluar")
            embed.set_author(**author_data)
            embed.set_thumbnail(url=str(user_data.display_avatar))
            modlog.embed = embed
        elif action == PotiaModLogAction.MEMBER_BAN:
            embed = discord.Embed(title="🔨 Anggota terbanned", color=0x8B0E0E, timestamp=current_time)
            ban_data = data["details"]
            embed.description = "\n".join(desc_data)
            if "executor" in ban_data:
                embed.add_field(name="Eksekutor", value=ban_data["executor"])
            embed.add_field(name="Alasan", value=f"```\n{ban_data['reason']}\n```", inline=False)
            embed.set_footer(text="🚪🔨 Banned")
            embed.set_author(**author_data)
            embed.set_thumbnail(url=str(user_data.display_avatar))
            modlog.embed = embed
        elif action == PotiaModLogAction.MEMBER_UNBAN:
            embed = discord.Embed(title="🔨👼 Anggota diunbanned", color=0x2BCEC2, timestamp=self.ctime())
            embed.description = "\n".join(desc_data)
            ban_data = data["details"]
            if "forgiver" in ban_data:
                embed.add_field(name="Pemaaf", value=ban_data["forgiver"])
            embed.set_footer(text="🚪👼 Unbanned")
            embed.set_author(**author_data)
            embed.set_thumbnail(url=str(user_data.display_avatar))
            modlog.embed = embed
        elif action == PotiaModLogAction.MEMBER_UPDATE:
            details = data["details"]
            role_change = "added" in details
            embed = discord.Embed(timestamp=current_time)
            if role_change:
                embed.title = "🤵 Perubahan Role"
                embed.colour = 0x832D64
                added_role_desc = list(map(lambda role: f"- **{role.name}** `[{role.id}]`", details["added"]))
                removed_role_desc = list(
                    map(lambda role: f"- **{role.name}** `[{role.id}]`", details["removed"])
                )
                if len(added_role_desc) > 0:
                    embed.add_field(name="🆕 Penambahan", value="\n".join(added_role_desc), inline=False)
                if len(removed_role_desc) > 0:
                    embed.add_field(name="❎ Dicabut", value="\n".join(removed_role_desc), inline=False)
                embed.set_footer(text="⚖ Perubahan Roles")
            else:
                old_nick, new_nick = details["old"], details["new"]
                nick_desc = []
                nick_desc.append(f"• Sebelumnya: **{old_nick if old_nick is not None else '*Tidak ada.*'}**")
                nick_desc.append(f"• Sekarang: **{new_nick if new_nick is not None else '*Dihapus.*'}**")
                embed.description = "\n".join(nick_desc)
                embed.set_footer(text="📎 Perubahan Nickname.")
            embed.set_author(**author_data)
            embed.set_thumbnail(url=str(user_data.display_avatar))
            modlog.embed = embed
        return modlog

    @commands.Cog.listener("on_member_join")
    async def _member_join_logging(self, member: discord.Member):
        should_log = self.bot.should_modlog(member.guild, member)
        if not should_log:
            return
        member_name = f"{member.name}#{member.discriminator} ({member.id})"
        self.logger.info(f"{member_name} joined the server, sending to modlogs...")
        modlog_data = self._generate_log(PotiaModLogAction.MEMBER_JOIN, {"user_data": member})
        await self.bot.send_modlog(modlog_data)

    @commands.Cog.listener("on_member_remove")
    async def _member_remove_logging(self, member: discord.Member):
        should_log = self.bot.should_modlog(member.guild, member)
        if not should_log:
            return
        member_name = f"{member.name}#{member.discriminator} ({member.id})"
        self.logger.info(f"{member_name} leave the server, sending to modlogs...")
        modlog_data = self._generate_log(PotiaModLogAction.MEMBER_LEAVE, {"user_data": member})
        await self.bot.send_modlog(modlog_data)

    @commands.Cog.listener("on_member_ban")
    async def _member_ban_logging(self, guild: discord.Guild, user: Union[discord.User, discord.Member]):
        should_log = self.bot.should_modlog(guild, user)
        if not should_log:
            return
        details_data = {}
        reason = "Tidak ada alasan."
        banned_by = None
        try:
            ban_data = await guild.fetch_ban(user)
            reason = ban_data.reason
            user_banner: discord.User = ban_data.user
            banned_by = f"{user_banner.mention} ({user_banner.id})"
        except (discord.Forbidden, discord.NotFound, discord.HTTPException, AttributeError):
            pass
        details_data["reason"] = reason
        if banned_by is not None:
            details_data["executor"] = banned_by

        modlog_data = self._generate_log(
            PotiaModLogAction.MEMBER_BAN, {"user_data": user, "details": details_data}
        )
        self.logger.info(
            f"A user has been banned: {user.name}#{user.discriminator} ({user.id}), sending to modlogs..."
        )
        await self.bot.send_modlog(modlog_data)

    @commands.Cog.listener("on_member_unban")
    async def _member_unban_logging(self, guild: discord.Guild, user: discord.User):
        should_log = self.bot.should_modlog(guild, user)
        if not should_log:
            return
        details_data = {}
        async for entry in guild.audit_logs(action=discord.AuditLogAction.unban):
            if entry.target.id == user.id:
                details_data = {"forgiver": f"{entry.user.mention} ({entry.user.id})"}
                break

        modlog_data = self._generate_log(
            PotiaModLogAction.MEMBER_UNBAN, {"user_data": user, "details": details_data}
        )
        self.logger.info(
            f"A user has been unbanned: {user.name}#{user.discriminator} ({user.id}), sending to modlogs..."
        )
        await self.bot.send_modlog(modlog_data)

    @commands.Cog.listener("on_member_update")
    async def _member_update_logging(self, before: discord.Member, after: discord.Member):
        should_log = self.bot.should_modlog(before.guild, before)
        if not should_log:
            return
        nick_updated = role_updated = False
        nick_detail = {}
        if before.nick != after.nick:
            nick_updated = True
            nick_detail["new"] = after.nick
            nick_detail["old"] = before.nick

        role_before, role_after = before.roles, after.roles
        role_detail = {}
        if len(role_before) != len(role_after):
            role_updated = True
            newly_added = []
            for aft in role_after:
                if aft not in role_before:
                    newly_added.append(aft)
            removed_role = []
            for bef in role_before:
                if bef not in role_after:
                    removed_role.append(bef)
            role_detail["added"] = newly_added
            role_detail["removed"] = removed_role

        if not role_updated and not nick_updated:
            return

        if nick_updated:
            self.logger.info("Nickname is updated, reporting to modlog...")
            generate_log = self._generate_log(
                PotiaModLogAction.MEMBER_UPDATE, {"user_data": after, "details": nick_detail}
            )
            await self.bot.send_modlog(generate_log)

        if role_updated:
            self.logger.info("Role updated, reporting to modlog...")
            generate_log = self._generate_log(
                PotiaModLogAction.MEMBER_UPDATE, {"user_data": after, "details": role_detail}
            )
            await self.bot.send_modlog(generate_log)


def setup(bot: PotiaBot):
    bot.add_cog(LoggingMember(bot))
