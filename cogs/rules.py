import logging
from typing import Dict, List

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


def setup(bot: PotiaBot):
    bot.add_cog(RulesHandler(bot))
