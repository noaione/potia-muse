import logging

import discord
from discord.ext import commands
from phelper.bot import PotiaBot
from phelper.modlog import PotiaModLog, PotiaModLogAction


class LoggingChannel(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("log.LoggingChannel")
        self._guild: discord.Guild = self.bot.get_guild(864004899783180308)

    def _generate_log(self, action: PotiaModLogAction, data: dict) -> PotiaModLog:
        current_time = self.bot.now()
        potia_log = PotiaModLog(action=action, timestamp=current_time)

        if action == PotiaModLogAction.CHANNEL_CREATE:
            embed = discord.Embed(
                "#️⃣ Kanal dibuat", color=discord.Color.from_rgb(63, 154, 115), timestamp=current_time
            )
            description = []
            description.append(f"**• Nama**: #{data['name']}")
            description.append(f"**• ID Kanal**: {data['id']} (<#{data['id']}>)")
            description.append(f"**• Tipe**: {data['type']}")
            description.append(f"**• Posisi**: {data['position'] +1}")
            description.append(f"**• Di kategori**: {data['category']}")
            embed.description = "\n".join(description)
            embed.set_footer(text="🏗 Kanal baru")
            if self._guild is not None:
                embed.set_thumbnail(url=str(self._guild.icon_url))
                embed.set_author(name=self._guild.name, icon_url=str(self._guild.icon_url))
            potia_log.embed = embed
        elif action == PotiaModLogAction.CHANNEL_DELETE:
            embed = discord.Embed(
                "#️⃣ Kanal dihapus", color=discord.Color.from_rgb(163, 68, 54), timestamp=current_time
            )
            description = []
            description.append(f"**• Nama**: #{data['name']}")
            description.append(f"**• ID Kanal**: {data['id']}")
            description.append(f"**• Tipe**: {data['type']}")
            description.append(f"**• Posisi**: {data['position'] +1}")
            description.append(f"**• Di kategori**: {data['category']}")
            embed.description = "\n".join(description)
            embed.set_footer(text="💣 Kanal dihapus")
            if self._guild is not None:
                embed.set_thumbnail(url=str(self._guild.icon_url))
                embed.set_author(name=self._guild.name, icon_url=str(self._guild.icon_url))
            potia_log.embed = embed
        elif action == PotiaModLogAction.CHANNEL_UPDATE:
            is_name_change = "before" in data
            embed = discord.Embed(color=discord.Color.from_rgb(94, 57, 159), timestamp=current_time)
            description = []
            if is_name_change:
                embed.title = "💈 Perubahan nama kanal"
                description.append(f"**• Sebelumnya**: #{data['before']}")
                description.append(f"**• Sekarang**: #{data['after']}")
                description.append(f"**• ID Kanal**: {data['id']} (<#{data['id']}>)")
            else:
                is_stonk = data["new"] > data["old"]
                if is_stonk:
                    embed.title = "📈 Perubahan posisi kanal"
                else:
                    embed.title = "📉 Perubahan posisi kanal"
                description.append(f"**• Sebelumnya**: Posisi #{data['old'] + 1}")
                description.append(f"**• Sekarang**: Posisi #{data['new'] + 1}")
                if "category" in data:
                    kategori = data["category"]
                    kategori_embed = []
                    kategori_embed.append(f"**• Kategori lama**: {kategori['before']}")
                    kategori_embed.append(f"**• Kategori baru**: {kategori['after']}")
                    embed.add_field(name="#️⃣ Perubahan kategori", value="\n".join(kategori_embed))
            description.append(f"**• Tipe**: {data['type']}")
            embed.description = "\n".join(description)
            if self._guild is not None:
                embed.set_thumbnail(url=str(self._guild.icon_url))
                embed.set_author(name=self._guild.name, icon_url=str(self._guild.icon_url))
            potia_log.embed = embed
        return potia_log

    @staticmethod
    def _determine_channel_type(channel: discord.abc.GuildChannel):
        if isinstance(channel, discord.TextChannel):
            if channel.is_news():
                return "📢 Kanal berita/pengumuman"
            return "💬 Kanal teks"
        elif isinstance(channel, discord.VoiceChannel):
            return "🔉 Kanal suara"
        elif isinstance(channel, discord.StageChannel):
            return "🎬 Kanal panggung"
        return None

    @commands.Cog.listener("on_guild_channel_update")
    async def _log_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ) -> None:
        should_log = self.bot.should_modlog(before)
        if not should_log:
            return

        determine = self._determine_channel_type(before)
        if determine is None:
            return

        base_info = {
            "id": str(before.id),
            "type": determine,
        }

        channel_moved = name_changed = False
        name_details = base_info
        if before.name != after.name:
            name_changed = True
            name_details["before"] = before.name
            name_details["after"] = after.name

        position_details = base_info
        if before.position != after.position:
            channel_moved = True
            category_before = before.category
            after_category = after.category
            category_data = {}
            if category_before is not None:
                category_data["before"] = category_before.name
            else:
                category_data["before"] = "*Tidak ada*"
            if after_category is not None:
                category_data["after"] = after_category.name
            else:
                category_data["after"] = "*Tidak ada*"

            position_details["old"] = before.position
            position_details["new"] = after.position
            if category_data["before"] != category_data["after"]:
                position_details["category"] = category_data

        if not name_changed and not channel_moved:
            return

        if name_changed:
            modlog = self._generate_log(PotiaModLogAction.CHANNEL_UPDATE, name_details)
            await self.bot.send_modlog(modlog)

        if channel_moved:
            modlog = self._generate_log(PotiaModLogAction.CHANNEL_UPDATE, position_details)
            await self.bot.send_modlog(modlog)

    @commands.Cog.listener("on_guild_channel_create")
    async def _log_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        should_log = self.bot.should_modlog(channel)
        if not should_log:
            return

        determine = self._determine_channel_type(channel)
        if determine is None:
            return

        details = {
            "type": determine,
            "name": channel.name,
            "id": channel.id,
            "position": channel.position,
            "category": channel.category.name if channel.category is not None else "*Tidak ada*",
        }

        modlog = self._generate_log(PotiaModLogAction.CHANNEL_CREATE, details)
        await self.bot.send_modlog(modlog)

    @commands.Cog.listener("on_guild_channel_delete")
    async def _log_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        should_log = self.bot.should_modlog(channel)
        if not should_log:
            return

        determine = self._determine_channel_type(channel)
        if determine is None:
            return

        details = {
            "type": determine,
            "name": channel.name,
            "id": channel.id,
            "position": channel.position,
            "category": channel.category.name if channel.category is not None else "*Tidak ada*",
        }

        modlog = self._generate_log(PotiaModLogAction.CHANNEL_DELETE, details)
        await self.bot.send_modlog(modlog)


def setup(bot: PotiaBot) -> None:
    bot.add_cog(LoggingChannel(bot))
