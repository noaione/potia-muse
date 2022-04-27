import logging
from io import BytesIO
from typing import List, Tuple

import discord
from discord.ext import commands
from discord.utils import _bytes_to_base64_data
from phelper.bot import PotiaBot
from phelper.welcomer import WelcomerCard


class UserWelcomer(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot

        self.logger = logging.getLogger("cogs.UserWelcomer")
        self._guild: discord.Guild = self.bot.get_guild(864004899783180308)

    async def _generate_image(self, _welcome_req: WelcomerCard):
        req_data = {
            "u": _welcome_req.username,
            "ud": _welcome_req.discriminator,
            "avatar": _welcome_req.avatar,
        }
        async with self.bot.aiosession.post(
            "https://naotimes-og.glitch.me/_gen/muse-welcome", json=req_data
        ) as resp:
            if resp.status != 200:
                return None
            image_data = await resp.read()
            return image_data

    async def _generate_messages_and_files(
        self, member: discord.Member
    ) -> Tuple[str, discord.Embed, discord.File]:
        guild_member: List[discord.Member] = self._guild.members
        real_members = 0
        for gm in guild_member:
            if gm.bot:
                continue
            if gm.id == member.id:
                continue
            real_members += 1

        self.logger.info(f"{member}: Welcoming member #{real_members + 1}, reading avatar...")
        wilkomen = WelcomerCard(member.name, member.discriminator, member.avatar.url)

        generated_img = await self._generate_image(wilkomen)

        self.logger.info(f"{member}: avatar generated, sending back result...")
        welcome_msg = f"Halo {member.mention}! Selamat datang di Peladen Resmi Muse Indonesia!\n"
        welcome_msg += f"Kamu adalah anggota **ke-{real_members + 1}**. "
        welcome_msg += "Jangan lupa baca <#864018800743940108> untuk mengakses "
        welcome_msg += "kanal lainnya, ya! Terima kasih!"

        embed = discord.Embed(title="Selamat datang!", timestamp=self.bot.now())
        embed.description = "Lihat <#864018800743940108> untuk mengakses kanal lainnya!"
        embed.set_footer(text="Masuk pada")
        image_file = None
        if generated_img is not None:
            image_file = discord.File(fp=BytesIO(generated_img), filename=f"WelcomeCard.{member.id}.png")
            embed.set_image(url=f"attachment://WelcomeCard.{member.id}.png")

        return welcome_msg, embed, image_file

    @commands.Cog.listener("on_member_join")
    async def _welcome_people(self, member: discord.Member):
        guild = self.bot.get_guild(864004899783180308)
        self._guild = guild
        welcome_gate: discord.TextChannel = guild.get_channel(864063431399964693)

        welcome_msg, welcome_embed, welcome_file = await self._generate_messages_and_files(member)
        if welcome_file is not None:
            await welcome_gate.send(content=welcome_msg, embed=welcome_embed, file=welcome_file)
        else:
            await welcome_gate.send(content=welcome_msg)

    @commands.command()
    @commands.is_owner()
    @commands.guild_only()
    async def testwuser(self, ctx: commands.Context):
        welcome_msg, welcome_embed, welcome_file = await self._generate_messages_and_files(ctx.author)
        if welcome_file is not None:
            await ctx.send(content=welcome_msg, embed=welcome_embed, file=welcome_file)
        else:
            await ctx.send(content=welcome_msg)

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def wscreen(self, ctx: commands.Context):
        guild = self.bot.get_guild(864004899783180308)
        welcome_screen = await guild.welcome_screen()
        print(welcome_screen)


def setup(bot: PotiaBot):
    bot.add_cog(UserWelcomer(bot))
