import logging

import discord
from discord.ext import commands
from phelper.bot import PotiaBot
from phelper.modlog import PotiaModLog, PotiaModLogAction


class LoggingThreads(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot: PotiaBot = bot
        self.logger = logging.getLogger("log.LoggingThreads")

    def _generate_log(self, action: PotiaModLogAction, data: dict) -> PotiaModLog:
        current_time = self.bot.now()
        potia_log = PotiaModLog(action=action, timestamp=current_time)
        guild_info = data.get("guild", None)

        if action == PotiaModLogAction.THREAD_CREATE:
            embed = discord.Embed(title="🗞 Thread dibuat", color=discord.Color.from_rgb(67, 154, 96))
            description = []
            description.append(f"**• Nama**: #{data['name']}")
            description.append(f"**• ID thread**: {data['id']} (<#{data['id']}>)")
            if data["channel"] is not None:
                description.append(f"**• Di kanal**: #{data['channel']}")
            embed.description = "\n".join(description)
            embed.set_footer(text="#️⃣ Thread baru")
            if guild_info is not None:
                embed.set_thumbnail(url=guild_info["icon"])
                embed.set_author(name=guild_info["name"], icon_url=guild_info["icon"])
            potia_log.embed = embed
        elif action == PotiaModLogAction.THREAD_REMOVE:
            embed = discord.Embed(title="🚮 Thread dihapus", color=discord.Color.from_rgb(176, 45, 45))
            description = []
            description.append(f"**• Nama**: #{data['name']}")
            description.append(f"**• ID thread**: {data['id']} (<#{data['id']}>)")
            if data["channel"] is not None:
                description.append(f"**• Dari kanal**: #{data['channel']}")
            embed.description = "\n".join(description)
            embed.set_footer(text="🚮 Thread dihapus")
            if guild_info is not None:
                embed.set_thumbnail(url=guild_info["icon"])
                embed.set_author(name=guild_info["name"], icon_url=guild_info["icon"])
            potia_log.embed = embed
        elif action == PotiaModLogAction.THREAD_UPDATE:
            embed = discord.Embed(title="💎 Perubahan thread", color=discord.Color.random())
            if "name" in data:
                name_detail = data["name"]
                name_desc = []
                name_desc.append(f"**• Sebelumnya**: #{name_detail['before']}")
                name_desc.append(f"**• Sekarang**: #{name_detail['after']}")
                embed.add_field(name="🔡 Perubahan Nama", value="\n".join(name_desc), inline=False)
            if "archive" in data:
                arch = data["archive"]
                arch_desc = []
                lock_k = "🔒"
                lock_ka = "*Thread diarchive*"
                if not arch["status"]:
                    lock_ka = "*Thread dibuka kembali*"
                    lock_k = "🔓"
                if "author" in arch:
                    arch_desc.append(f"**• Pelaku**: {arch['author']}")
                arch_desc.append(f"**• Pada**: {self.strftime(arch['timestamp'])}")
                embed.add_field(name=f"{lock_k} {lock_ka}", value="\n".join(arch_desc), inline=False)
            if guild_info is not None:
                embed.set_thumbnail(url=guild_info["icon"])
                embed.set_author(name=guild_info["name"], icon_url=guild_info["icon"])
            if data["channel"] is not None:
                embed.description = f"**• Di kanal**: #{data['channel']}"
            potia_log.embed = embed

        return potia_log

    @commands.Cog.listener("on_thread_join")
    async def _log_thread_join(self, thread: discord.Thread):
        should_log = self.bot.should_modlog(thread.guild)
        if not should_log:
            return

        guild = thread.guild
        parent = thread.parent
        parent_name = None
        if parent is not None:
            parent_name = parent.name

        details = {
            "name": thread.name,
            "id": thread.id,
            "channel": parent_name,
            "guild": {"name": guild.name, "icon": str(guild.icon)},
        }

        modlog = self._generate_log(PotiaModLogAction.THREAD_CREATE, details)
        await self.bot.send_modlog(modlog)

    @commands.Cog.listener("on_thread_delete")
    async def _log_thread_delete(self, thread: discord.Thread):
        should_log = self.bot.should_modlog(thread.guild)
        if not should_log:
            return

        guild = thread.guild
        parent = thread.parent
        parent_name = None
        if parent is not None:
            parent_name = parent.name

        details = {
            "name": thread.name,
            "id": thread.id,
            "channel": parent_name,
            "guild": {"name": guild.name, "icon": str(guild.icon)},
        }

        modlog = self._generate_log(PotiaModLogAction.THREAD_REMOVE, details)
        await self.bot.send_modlog(modlog)

    @commands.Cog.listener("on_thread_update")
    async def _log_thread_update(self, before: discord.Thread, after: discord.Thread):
        should_log = self.bot.should_modlog(before.guild)
        if not should_log:
            return

        guild = before.guild
        parent = before.parent
        parent_name = None
        if parent is not None:
            parent_name = parent.name
        if parent_name is None and after.parent is not None:
            parent_name = after.parent.name

        details = {}
        name_details = {}
        if before.name != after.name:
            name_details["before"] = before.name
            name_details["after"] = after.name
            details["name"] = name_details
        archive_details = {}
        if before.archived != after.archived:
            archive_details["status"] = after.archived
            if after.archived:
                archiver_id = after.archiver_id
                if archiver_id is None:
                    archive_details["author"] = "*Archive otomatis oleh Discord*"
                else:
                    member_info = guild.get_member(archiver_id)
                    if member_info is None:
                        archive_details["author"] = "*Archive otomatis oleh Discord*"
                    else:
                        archive_details["author"] = f"{str(member_info)} (`{member_info.id}`)"
                archive_details["timestamp"] = after.archive_timestamp
            else:
                archive_details["timestamp"] = self.bot.now()
            details["archive"] = archive_details

        if "name" not in details and "archive" not in details:
            return

        details["guild"] = {"name": guild.name, "icon": str(guild.icon)}
        details["channel"] = parent_name

        modlog = self._generate_log(PotiaModLogAction.THREAD_UPDATE, details)
        await self.bot.send_modlog(modlog)


def setup(bot: PotiaBot):
    bot.add_cog(LoggingThreads(bot))
