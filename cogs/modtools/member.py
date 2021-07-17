import logging

import discord
from discord.ext import commands
from phelper.bot import PotiaBot
from phelper.modlog import PotiaModLog, PotiaModLogAction
from phelper.utils import rounding


class ModToolsMember(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("ModTools.Member")
        self._shadowbanned = []
        self._guild = 864004899783180308
        self._redis_id = "potiamuse_shadowban"

    async def initialize(self):
        self.logger.info("Collecting shadowbanned user on Muse server...")
        all_shadowbanned: list = await self.bot.redis.get(self._redis_id, [])
        self.logger.info(f"Found: {len(all_shadowbanned)} member is shadowbanned.")
        self._shadowbanned = all_shadowbanned

    @commands.Cog.listener("on_member_join")
    async def _watch_shadowbanned_user(self, guild: discord.Guild, member: discord.Member):
        if guild.id == self._guild:
            if str(member.id) in self._shadowbanned:
                self.logger.info("Member is shadowbanned on this guild, banning!")
                await guild.ban(member, reason="User is shadowbanned.")

    async def _internal_shadowban(self, user_id: int, action: str = "BAN"):
        action = action.upper()
        user_id = str(user_id)
        if action == "BAN":
            if user_id not in self._shadowbanned:
                self._shadowbanned.append(user_id)
                await self.bot.redis.set(self._redis_id, self._shadowbanned)
                return True
        elif action == "UNBAN":
            if user_id in self._shadowbanned:
                self._shadowbanned.remove(user_id)
                await self.bot.redis.set(self._redis_id, self._shadowbanned)
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
            embed.set_author(name=str(self.bot.user), icon_url=self.bot.user.avatar_url)
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
            embed.set_author(name=str(self.bot.user), icon_url=self.bot.user.avatar_url)
            description = f"**• User ID**: {user_id}\n"
            description += f"**• Pada**: <t:{rounding(current_time.timestamp())}:F>\n"
            description += f"**• Pemaaf**: {ctx.author.mention} ({ctx.author.id})"
            embed.description = description
            embed.set_footer(text="🛡🔨🕶 Unshadowban")
            potia_log.embed = embed
            potia_log.timestamp = current_time.timestamp()
            await self.bot.send_modlog(potia_log)


def setup(bot: PotiaBot):
    bot.add_cog(ModToolsMember(bot))
