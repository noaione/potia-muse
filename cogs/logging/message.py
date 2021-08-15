import logging
from typing import List, Union

import discord
from discord.ext import commands, tasks
from phelper.bot import PotiaBot
from phelper.modlog import PotiaModLog, PotiaModLogAction


class LoggingMessage(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("log.LoggingMessage")
        self._guild: discord.Guild = self.bot.get_guild(864004899783180308)
        self._init_start.start()

    def cog_unload(self):
        self._init_start.cancel()

    @tasks.loop(seconds=1, count=1)
    async def _init_start(self):
        self._guild = self.bot.get_guild(864004899783180308)

    @_init_start.before_loop
    async def _init_start_before(self):
        await self.bot.wait_until_ready()

    async def _upload_or_not(self, content: str, force_upload: bool = False):
        if not isinstance(content, str):
            return "", False
        if len(content) > 1995 or force_upload:
            return await self.bot.upload_ihateanime(content, "MessageLog.txt"), True
        return content, False

    @staticmethod
    def truncate(msg: str, limit: int) -> str:
        if len(msg) <= limit:
            return msg
        msg = msg[: limit - 8] + " [...]"
        return msg

    def _generate_log(self, action: PotiaModLogAction, data: dict):
        current = self.bot.now()
        potia_log = PotiaModLog(action=action, timestamp=current.timestamp())
        if action == PotiaModLogAction.MESSAGE_DELETE:
            channel_info = data["channel"]
            uinfo = data["author"]
            embed = discord.Embed(title="🚮 Pesan dihapus", color=0xD66B6B, timestamp=current)
            embed.description = data["content"]
            embed.set_author(name=f"{uinfo['name']}", icon_url=uinfo["avatar"])
            embed.set_footer(text=f"❌ Kanal #{channel_info['name']}")
            if "executor" in data:
                exegs = data["executor"]
                embed.add_field(name="Pembersih", value=f"<@{exegs['id']}> ({exegs['id']})", inline=False)
            if "thumbnail" in data:
                embed.set_image(url=data["thumbnail"])
            if "attachments" in data:
                attachments = data["attachments"]
                embed.add_field(name="Attachments", value=attachments, inline=False)
            potia_log.embed = embed
        elif action == PotiaModLogAction.MESSAGE_DELETE_BULK:
            embed = discord.Embed(
                title=f"🚮 {data['count']} Pesan dihapus",
                color=discord.Color.from_rgb(199, 46, 69),
                timestamp=current,
            )
            channel_info = data["channel"]
            new_desc = "*Semua pesan yang dihapus telah diunggah ke link berikut:*\n"
            new_desc += embed["url"] + "\n\n*Link valid selama kurang lebih 2.5 bulan*"
            embed.description = new_desc
            if "executor" in data:
                exegs = data["executor"]
                embed.add_field(name="Pembersih", value=f"<@{exegs['id']}> ({exegs['id']})", inline=False)
            embed.set_author(name=f"#{channel_info['name']}", icon_url=str(self._guild.icon))
            embed.set_footer(text=f"❌ Kanal #{channel_info['name']}")
            potia_log.embed = embed
        elif action == PotiaModLogAction.MESSAGE_EDIT:
            user_data = data["author"]
            kanal_name = data["channel"]["name"]
            before, after = data["before"], data["after"]
            embed = discord.Embed(title="📝 Pesan diubah", color=0xE7DC8C, timestamp=current)
            embed.add_field(name="Sebelum", value=self.truncate(before, 1024), inline=False)
            embed.add_field(name="Sesudah", value=self.truncate(after, 1024), inline=False)
            embed.set_footer(text=f"📝 Kanal #{kanal_name}")
            if "thumbnail" in data:
                embed.set_image(url=data["thumbnail"])
            embed.set_author(name=user_data["name"], icon_url=user_data["avatar"])
            potia_log.embed = embed
        return potia_log

    @commands.Cog.listener("on_message_edit")
    async def _log_message_edit(self, before: discord.Message, after: discord.Message):
        should_log = self.bot.should_modlog(before.guild, before.author)
        if not should_log:
            return

        if after.is_system():
            return

        if before.content == after.content:
            return

        details = {
            "author": {
                "id": before.author.id,
                "name": before.author.name,
                "avatar": str(before.author.avatar),
            },
            "channel": {"id": before.channel.id, "name": before.channel.name},
            "before": before.content,
            "after": after.content,
        }
        if len(before.attachments) > 0:
            img_attach = None
            for att in before.attachments:
                if att.content_type.startswith("image/"):
                    img_attach = att
                    break
            if img_attach is not None:
                details["thumbnail"] = img_attach
        if "thumbnail" not in details and len(after.attachments) > 0:
            img_attach = None
            for att in after.attachments:
                if att.content_type.startswith("image/"):
                    img_attach = att
                    break
            if img_attach is not None:
                details["thumbnail"] = img_attach

        self.logger.info(f"Message edited on #{before.channel.name}, sending to modlog...")
        modlog = self._generate_log(PotiaModLogAction.MESSAGE_EDIT, details)
        await self.bot.send_modlog(modlog)

    @commands.Cog.listener("on_message_delete")
    async def _log_message_delete(self, message: discord.Message):
        should_log = self.bot.should_modlog(message.guild, message.author)
        if not should_log:
            return

        if message.is_system():
            return

        guild: discord.Guild = message.guild
        initiator: Union[discord.Member, discord.User] = None
        async for guild_log in guild.audit_logs(action=discord.AuditLogAction.message_delete):
            if guild_log.user.id == message.author.id:
                initiator = guild_log.target
                break

        if initiator is not None and initiator.bot:
            # Dont log if message got deleted by bot.
            return

        real_content, use_iha = await self._upload_or_not(message.content)
        if use_iha:
            mod_content = "*Dikarenakan teks terlalu panjang, isinya telah diunggah ke link berikut:* "
            mod_content += real_content + "\n"
            mod_content += "Link valid kurang lebih untuk 2.5 bulan!"
            real_content = mod_content

        if not real_content:
            real_content = "*Tidak ada konten*"

        details = {
            "channel": {
                "id": message.channel.id,
                "name": message.channel.name,
            },
            "author": {
                "id": message.author.id,
                "name": str(message.author),
                "avatar": str(message.author.avatar),
            },
            "content": real_content,
        }
        if len(message.attachments) > 0:
            img_attach = None
            for att in message.attachments:
                if att.content_type.startswith("image/"):
                    img_attach = att
                    break
            all_attachment = []
            if img_attach is not None:
                details["thumbnail"] = img_attach
            for xxy, attach in enumerate(message.attachments, 1):
                all_attachment.append(f"**#{xxy}.** {attach.filename}")
            details["attachments"] = "\n".join(all_attachment)
        if initiator is not None:
            details["executor"] = {
                "id": initiator.id,
                "name": str(initiator),
            }

        self.logger.info(f"Message deleted from: {message.author}, sending to modlog...")
        log_gen = self._generate_log(PotiaModLogAction.MESSAGE_DELETE, details)
        await self.bot.send_modlog(log_gen)

    @commands.Cog.listener("on_bulk_message_delete")
    async def _log_bulk_message_delete(self, messages: List[discord.Message]):
        valid_messages: List[discord.Message] = []
        for message in messages:
            should_log = self.bot.should_modlog(message.guild, message.author)
            if not should_log:
                return
            if message.is_system():
                continue
            valid_messages.append(message)

        executor = {}
        async for audit in self._guild.audit_logs(action=discord.AuditLogAction.message_bulk_delete):
            if audit.extra is not None and len(audit.extra.count) == len(valid_messages):
                executor = {
                    "id": audit.user.id,
                    "name": str(audit.user),
                }
                break

        full_upload_text = []
        channel = valid_messages[0].channel
        for n, message in enumerate(valid_messages, 1):
            current = []
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S") + " UTC"
            current.append(f"-- Pesan #{n} :: {str(message.author)} ({message.author.id}) [{timestamp}]")
            konten = message.content
            if not isinstance(konten, str):
                konten = "*Tidak ada konten*"
            if not konten:
                konten = "*Tidak ada konten*"
            current.append(konten)
            if len(message.attachments) > 0:
                current.append("")
                current.append("*Attachments*:")
                for xyz, attachment in enumerate(message.attachments, 1):
                    current.append(
                        f"Attachment #{xyz}: {attachment.filename} "
                        + "({attachment.proxy_url}) ({attachment.url})"
                    )
            full_upload_text.append("\n".join(current))

        real_content, _ = await self._upload_or_not("\n\n".join(full_upload_text), True)
        full_details = {
            "count": len(valid_messages),
            "url": real_content,
            "channel": {
                "id": channel.id,
                "name": channel.name,
            },
        }
        if len(executor.keys()) > 0:
            full_details["executor"] = executor

        self.logger.info("Multiple message got deleted, sending to modlog...")
        log_gen = self._generate_log(PotiaModLogAction.MESSAGE_DELETE_BULK, full_details)
        await self.bot.send_modlog(log_gen)


def setup(bot: PotiaBot):
    bot.add_cog(LoggingMessage(bot))
