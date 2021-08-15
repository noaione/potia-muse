import logging
from typing import List

import discord
from discord.ext import commands, tasks
from phelper.bot import PotiaBot
from phelper.modlog import PotiaModLog, PotiaModLogAction
from phelper.timeparse import TimeString, TimeStringParseError
from phelper.utils import rounding


class ModToolsMember(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("ModTools.Member")
        self._shadowbanned = []
        self._currently_muted = []
        self._guild_id = 864004899783180308
        self._guild: discord.Guild = None
        self._mute_role: discord.Role = None

        self._rdsb_id = "potiamuse_shadowban"

        self._mute_check_locked = False

        self.initialize.start()
        self.watch_mute_timeout.start()

    def cog_unload(self):
        self.initialize.cancel()
        self.watch_mute_timeout.cancel()

    @tasks.loop(count=1, seconds=1)
    async def initialize(self):
        self._guild = self.bot.get_guild(self._guild_id)
        self._mute_role = self._guild.get_role(866180421196447765)
        self.logger.info("Collecting shadowbanned user on Muse server...")
        all_shadowbanned: list = await self.bot.redis.get(self._rdsb_id, [])
        self.logger.info(f"Found: {len(all_shadowbanned)} member is shadowbanned.")
        self._shadowbanned = all_shadowbanned
        self.logger.info("Collecting all currently muted member...")
        all_currently_muted: List[dict] = await self.bot.redis.getall("potiamuse_muted_*")
        current_ts = self.bot.now().timestamp()
        for currently_mute in all_currently_muted:
            if "max" not in currently_mute:
                self._currently_muted.append(currently_mute)
                continue
            if current_ts < currently_mute["max"]:
                self._currently_muted.append(currently_mute)

    @initialize.before_loop
    async def _before_init(self):
        await self.bot.wait_until_ready()

    def find_muted_user(self, user_id: int):
        muted_member = list(filter(lambda x: x["id"] == str(user_id), self._currently_muted))
        if len(muted_member) > 0:
            return muted_member[0]
        return None

    @tasks.loop(seconds=1)
    async def watch_mute_timeout(self):
        if self._mute_check_locked:
            return
        self._mute_check_locked = True
        try:
            current_ts = self.bot.now().timestamp()
            for muted in self._currently_muted:
                if "max" not in muted:
                    # Forever muted, sadge
                    continue
                if current_ts > muted["max"]:
                    self.logger.info(f"Unmuting user: {muted['id']}")
                    await self.bot.redis.delete("potiamuse_muted_" + muted["id"])
                    member: discord.Member = self._guild.get_member(int(muted["id"]))
                    if member is not None:
                        try:
                            await member.remove_roles(self._mute_role, reason="Timed mute expired.")
                            self.logger.info(f"User {muted['id']} unmuted.")
                        except discord.Forbidden:
                            self.logger.warning("Failed to remove role because of missing permissions.")
                        except discord.HTTPException:
                            self.logger.error("An HTTP exception occured while trying to unmute this user!")
        except Exception:
            pass
        self._mute_check_locked = False

    @commands.Cog.listener("on_member_join")
    async def _watch_user_missing_and_shit(self, guild: discord.Guild, member: discord.Member):
        if guild.id == self._guild_id:
            if str(member.id) in self._shadowbanned:
                self.logger.info("Member is shadowbanned on this guild, banning!")
                await guild.ban(member, reason="User is shadowbanned.")

            muted_member = self.find_muted_user(str(member.id))
            if muted_member is not None:
                self.logger.info("Member was muted, checking mute expiration...")
                current_ts = self.bot.now().timestamp()
                first_occurence = muted_member[0]
                if "max" in first_occurence:
                    if first_occurence["max"] > current_ts:
                        self.logger.info("Member is doing mute evasion, remuting...")
                        try:
                            await member.add_roles(self._mute_role, reason="Mute evasion, remutting")
                            self.logger.info(f"User {first_occurence['id']} remuted again.")
                        except discord.Forbidden:
                            self.logger.warning("Failed to remove role because of missing permissions.")
                        except discord.HTTPException:
                            self.logger.error("An HTTP exception occured while trying to unmute this user!")
                else:
                    self.logger.info("Member is doing mute evasion, remuting...")
                    try:
                        await member.add_roles(self._mute_role, reason="Mute evasion, remutting")
                        self.logger.info(f"User {first_occurence['id']} remuted again.")
                    except discord.Forbidden:
                        self.logger.warning("Failed to remove role because of missing permissions.")
                    except discord.HTTPException:
                        self.logger.error("An HTTP exception occured while trying to unmute this user!")

    async def _internal_shadowban(self, user_id: int, action: str = "BAN"):
        action = action.upper()
        user_id = str(user_id)
        if action == "BAN":
            if user_id not in self._shadowbanned:
                self._shadowbanned.append(user_id)
                await self.bot.redis.set(self._rdsb_id, self._shadowbanned)
                return True
        elif action == "UNBAN":
            if user_id in self._shadowbanned:
                self._shadowbanned.remove(user_id)
                await self.bot.redis.set(self._rdsb_id, self._shadowbanned)
                return True
        return False

    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def shadowban(self, ctx: commands.Context, user_id: int):
        success_log = await self._internal_shadowban(user_id)
        msg = f"🔨 Palu dilayangkan untuk user ID: `{user_id}`\n"
        msg += "Jika user tersebut masuk ke peladen ini, user tersebut akan otomatis di ban!"
        await ctx.send(msg)
        if success_log:
            potia_log = PotiaModLog(PotiaModLogAction.MEMBER_SHADOWBAN)
            current_time = self.bot.now()
            embed = discord.Embed(title="🔨 Shadowbanned", timestamp=current_time)
            embed.set_author(name=str(self.bot.user), icon_url=self.bot.user.avatar)
            description = f"**• User ID**: {user_id}\n"
            description += f"**• Pada**: <t:{rounding(current_time.timestamp())}:F>\n"
            description += f"**• Tukang palu**: {ctx.author.mention} ({ctx.author.id})"
            embed.description = description
            embed.set_footer(text="🔨🕶 Shadowbanned")
            potia_log.embed = embed
            potia_log.timestamp = current_time.timestamp()
            await self.bot.send_modlog(potia_log)

    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def unshadowban(self, ctx: commands.Context, user_id: int):
        success_log = await self._internal_shadowban(user_id, "UNBAN")
        msg = f"🛡 Palu ban diambil kembali untuk user ID: `{user_id}`\n"
        msg += "Jika user tersebut masuk ke peladen ini, user tersebut tidak akan di ban otomatis."
        await ctx.send(msg)
        if success_log:
            potia_log = PotiaModLog(PotiaModLogAction.MEMBER_UNSHADOWBAN)
            current_time = self.bot.now()
            embed = discord.Embed(title="🛡🔨 Unshadowban", timestamp=current_time)
            embed.set_author(name=str(self.bot.user), icon_url=self.bot.user.avatar)
            description = f"**• User ID**: {user_id}\n"
            description += f"**• Pada**: <t:{rounding(current_time.timestamp())}:F>\n"
            description += f"**• Pemaaf**: {ctx.author.mention} ({ctx.author.id})"
            embed.description = description
            embed.set_footer(text="🛡🔨🕶 Unshadowban")
            potia_log.embed = embed
            potia_log.timestamp = current_time.timestamp()
            await self.bot.send_modlog(potia_log)

    @commands.command()
    @commands.has_guild_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def mute(
        self, ctx: commands.Context, member: commands.MemberConverter, *, full_reasoning: str = None
    ):
        if not isinstance(member, discord.Member):
            return await ctx.send("⁉ User yang anda pilih bukanlah member server ini!")

        if member.guild.id != self._guild_id:
            return await ctx.send("⁉ User yang anda pilih bukanlah member server ini!")

        if member.bot:
            return await ctx.send("🤖 Member tersebut adalah bot! Jadi tidak bisa di mute!")

        already_muted = await self.find_muted_user(member.id)
        if already_muted is not None:
            return await ctx.send("❓ User sudah dimute!")

        if not isinstance(full_reasoning, str):
            full_reasoning = "Muted by bot"

        split_reason = full_reasoning.split(" ", 1)
        timeout = None
        reason = full_reasoning
        if len(split_reason) > 1:
            try:
                timeout = TimeString.parse(split_reason[0])
                reason = split_reason[1]
            except TimeStringParseError:
                pass

        target_top_role: discord.Role = member.top_role
        my_top_role: discord.Role = ctx.author.top_role

        if target_top_role > my_top_role:
            return await ctx.send("🤵 User tersebut memiliki tahkta yang lebih tinggi daripada anda!")

        if timeout is None:
            try:
                return await ctx.send("😶 User berhasil dimute!")
            except discord.Forbidden:
                return await ctx.send("❌ User gagal dimute, mohon cek bot-log!")

        timed_mute = {
            "id": str(member.id),
        }
        if timeout is not None:
            max_time = self.bot.now().timestamp() + timeout.timestamp()
            timed_mute["max"] = max_time

        try:
            self.logger.info(f"Muting {str(member)} for {str(timeout)}")
            await member.add_roles(self.bot.mute_role, reason=reason)
            self.logger.info(f"Successfully muted {str(member)}")
        except discord.Forbidden:
            self.logger.error("Bot doesn't have the access to mute that member")
            return await ctx.send("❌ Bot tidak dapat ngemute member tersebut!")
        except discord.HTTPException:
            return await ctx.send("❌ User gagal dimute, mohon cek bot-log!")

        await self.bot.redis.set(f"potiamuse_muted_{member.id}", timed_mute)
        self._currently_muted.append(timed_mute)
        await ctx.send("🔇 User berhasil dimute!")

    @commands.command()
    @commands.has_guild_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def unmute(self, ctx: commands.Context, member: commands.MemberConverter):
        if not isinstance(member, discord.Member):
            return await ctx.send("⁉ User yang anda pilih bukanlah member server ini!")

        if member.guild.id != self._guild_id:
            return await ctx.send("⁉ User yang anda pilih bukanlah member server ini!")

        is_muted = self.find_muted_user(member.id)
        if is_muted is None:
            return await ctx.send("❓ User belum dimute!")

        try:
            await member.remove_roles(self._mute_role, reason=f"Unmuted by {str(ctx.author)}")
            self.logger.info(f"User {str(member)} unmuted.")
        except discord.Forbidden:
            self.logger.warning("Failed to remove role because of missing permissions.")
            return await ctx.send("❌ Bot tidak dapat unmute member tersebut!")
        except discord.HTTPException:
            self.logger.error("An HTTP exception occured while trying to unmute this user!")
            return await ctx.send("❌ User gagal diunmute, mohon cek bot-log!")

        await self.bot.redis.delete(f"potiamuse_muted_{member.id}")
        try:
            self._currently_muted.remove(is_muted)
        except ValueError:
            pass
        await ctx.send("🔊 User berhasil diunmute!")


def setup(bot: PotiaBot):
    bot.add_cog(ModToolsMember(bot))
