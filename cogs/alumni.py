import logging
from typing import List

import discord
from discord.ext import commands
from phelper.bot import PotiaBot


class AlumniRole:
    _VALID_MEMBER_ROLE = [
        880773390305206276,
        880773390305206275,
        880773390305206274,
    ]
    _ALUMNUS_ID = 890102605789937745

    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    def _has_any_role(self, role_sets: List[discord.Role]):
        for role in role_sets:
            if role.id in self._VALID_MEMBER_ROLE:
                return True
        return False

    def _has_alumnus_role(self, role_sets: List[discord.Role]):
        for role in role_sets:
            if role.id == self._ALUMNUS_ID:
                return True
        return False

    @commands.Cog.listener("on_member_update")
    async def _member_alumni_role_auto(self, before: discord.Member, after: discord.Member):
        if before.guild.id != 864004899783180308:
            return
        muse_guild = before.guild
        role_before, role_after = before.roles, after.roles
        if self._has_any_role(role_before) or self._has_any_role(role_after):
            self.logger.info(f"User {before} have a member role, giving alumnus role...")
            if self._has_alumnus_role(role_before) or self._has_alumnus_role(role_after):
                self.logger.info(f"User {before} already have alumnus role, skipping...")
                return
            alumnus_role = muse_guild.get_role(890102605789937745)
            await after.add_roles(alumnus_role)
            self.logger.info(f"User {before} got their alumnus role!")

    @commands.command(name="berialumni")
    @commands.guild_only()
    async def _beri_alumni_cmd(self, ctx: commands.Context, target: commands.MemberConverter):
        """
        Beri alumni role kepada user yang memiliki member role.
        """
        if ctx.guild.id != 864004899783180308:
            return
        if not isinstance(target, discord.Member):
            return await ctx.send("Bukanlah sebuah member!")
        member_target: discord.Member = target
        if self._has_alumnus_role(member_target.roles):
            await ctx.send("Member sudah termasuk alumni!")
            return

        alumnus_role = member_target.guild.get_role(self._ALUMNUS_ID)
        await member_target.add_roles(alumnus_role)
        await ctx.send("Member diberikan role Alumni!")

    @commands.command(name="berisemuaalumni")
    @commands.guild_only()
    async def _beri_semua_alumni_cmd(self, ctx: commands.Context):
        """
        Beri alumni role kepada semua member yang memiliki member role.
        """
        guild: discord.Guild = ctx.guild
        if guild.id != 864004899783180308:
            return

        members: List[discord.Member] = guild.members
        members_with_valid_roles: List[discord.Member] = []
        for member in members:
            if self._has_any_role(member.roles):
                members_with_valid_roles.append(member)

        total_member = len(members_with_valid_roles)
        pesan = await ctx.send(f"Memberikan role Alumni untuk {total_member} member...")

        alumnus_role = guild.get_role(self._ALUMNUS_ID)
        added_roles = 0
        for idx, member in enumerate(members_with_valid_roles, 1):
            self.logger.info(f"Giving {member} an alumnus role ({idx}/{total_member})...")
            try:
                await member.add_roles(alumnus_role)
                added_roles += 1
            except discord.HTTPException:
                self.logger.warning(f"Failed to give {member} an alumnus role!")
        await pesan.edit(content=f"Berhasil menambah role Alumni untuk {added_roles}")
