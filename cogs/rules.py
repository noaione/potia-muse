import logging
from typing import Dict, List
import discord

from discord.ext import commands, tasks
from phelper.bot import PotiaBot

DEFAULT_RULES = """✦ Dilarang TOKSIK dan/atau MEMBULLY!
    Toksik yang dimaksud:
       - Capslock tidak pada tempatnya.
       - OOT (Keluar topik pembicaraan).
       - Menjatuhkan dan mengganggu orang lain.
       - Berkata kasar dan tidak senonoh.
       - Menghina orang lain.
       - Memanas-manasi, memprovokasi, atau menimbulkan konflik lebih lanjut.
✦ Dilarang keras membicarakan hal-hal yang berhubungan dengan SARA (Suku, Agama, Ras, dan Antargolongan), rasisme, politik, pelecehan seksual, menyampah, dan topik tidak mengenakkan yang membuat anggota lain tidak nyaman.
✦ Dilarang keras DOXXING!
✦ Dilarang menyebarkan rumor dan menggosip tentang pihak mana pun.
✦ Dilarang mengunggah atau membagikan hal-hal berbau gore, ataupun hal yang bisa memicu orang lain (memicu rasa takut, cemas, trauma, dan perasaan tidak nyaman lainnya).
✦ Dilarang membawa masalah luar ke dalam peladen ini, juga sebaliknya.
✦ Dilarang bertengkar, sengaja memulai kericuhan, atau memprovokasi! Dilarang memancing keributan. Jika ada yang bermasalah, silakan selesaikan masalah tersebut via japri (Direct/Personal Messages).
✦ Dilarang melakukan ancaman dan/atau pelecehan ke pihak mana pun.
"""  # noqa: E501

DEFAULT_MEMBER_INFO = """
Untuk mengakses kanal lainnya, kamu harus bergabung ke [membership Muse Indonesia](https://www.youtube.com/channel/UCxxnxya_32jcKj4yN1_kD7A/join) di YouTube terlebih dahulu!

Tier membership minimum untuk bergabung yaitu **MuStar**.

Setelah itu kamu harus menghubungkan akun Discord kamu dengan akun YouTube kamu.
Silakan ikuti langkah berikut:
1. Buka `User Settings`
2. Klik `Connections`
3. Lalu klik logo <:vtBYT:843473930348920832>
4. Pastikan kamu masuk dengan akun yang benar!

Jika sudah, mohon tunggu kurang lebih 24 jam.
Info lebih lanjut, silakan klik [pranala](https://support.discord.com/hc/en-us/articles/215162978-Youtube-Channel-Memberships-Integration-FAQ) berikut.

Jika mengalami kendala, kamu dapat menghubungi salah satu <@&864010032308027392>

**DIMOHON UNTUK TIDAK MENGHUBUNGI <@&864010509366984724> SAMA SEKALI! (TERMASUK MEMINTA PERTEMANAN!)**
"""  # noqa: E501

ALUMNI_INFO = """
Role <@&890102605789937745> merupakan role permanen yang diberikan jika anda pernah join
membership Muse Indonesia di YouTube.

Role ini berfungsi sebagai role agar anda tetap bisa nimbrung dengan member lain tanpa harus perpanjang.

Untuk mendapatkannya, pastikan anda telah mengikuti membership Muse Indonesia minimal `MuStar`, lalu
anda cukup menggunakan perintah `p/alumni` di DM bot <@864027281923506176>.

Contoh dapat anda lihat di sini:
"""
_MUSE_LOGO = "https://yt3.ggpht.com/ytc/AKedOLRKt9lXp2AafYyZvIIbciGQPq0j1c1bMrmaqAUs=s0-c-k-c0x00ffffff-no-rj"  # noqa: E501


class RulesHandler(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("cogs.RulesHandler")
        self._rules = []
        self._rules_map: Dict[str, Dict[str, str]] = {}
        self._rule_channel = 864018800743940108
        self.initialize_rules.start()

    def cog_unload(self):
        self.initialize_rules.cancel()

    @tasks.loop(seconds=1, count=1)
    async def initialize_rules(self):
        self.logger.info("Initializing rules...")
        rules_sets: List[str] = await self.bot.redis.get("potiarules", [])
        if not rules_sets:
            self.logger.info("Initiating with default rules...")
            split_rules = DEFAULT_RULES.split("\n✦")
            for rule in split_rules:
                if not rule.startswith("✦"):
                    rule = "✦" + rule
                rule = rule.rstrip("\n")
                self._rules.append(rule)
            await self.bot.redis.set("potiarules", self._rules)
        else:
            self.logger.info("Initiating with rules from redis...")
            for rule in rules_sets:
                self._rules.append(rule)

        self.logger.info("Preparing the message data...")
        messages_lists = await self.bot.redis.get("potiamrules_mapping", {})
        if len(messages_lists.keys()) > 0:
            self._rules_map = messages_lists
        self.logger.info("Initialization complete!")

    @commands.command()
    @commands.is_owner()
    async def debugrule(self, ctx: commands.Context):
        await ctx.send(f"There's {len(self._rules)} rules in the bot")

    @commands.command()
    @commands.is_owner()
    async def attachgiftutor(self, ctx: commands.Context):
        channel: discord.TextChannel = self.bot.get_channel(self._rule_channel)
        message = await channel.fetch_message(877891349163155476)

        the_embed = discord.Embed.from_dict(message.embeds[0].to_dict())
        the_embed.set_image(
            url="https://cdn.discordapp.com/attachments/761920289579204608/878977683537666048/FINAL.gif"
        )
        await message.edit(embed=the_embed)

    @commands.command()
    @commands.is_owner()
    async def update_rule_info(self, ctx: commands.Context):
        channel: discord.TextChannel = self.bot.get_channel(self._rule_channel)
        message = await channel.fetch_message(877891349163155476)
        the_embed = discord.Embed.from_dict(message.embeds[0].to_dict())
        the_embed.description = DEFAULT_MEMBER_INFO
        await message.edit(embed=the_embed)


def setup(bot: PotiaBot):
    bot.add_cog(RulesHandler(bot))
