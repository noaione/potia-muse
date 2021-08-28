import logging
from datetime import datetime, timezone
from typing import Dict, List, Union

import discord
from discord.ext import commands, tasks
from discord.raw_models import RawReactionActionEvent
from phelper.bot import PotiaBot
from phelper.utils import confirmation_dialog


def try_get(data: dict, key: str):
    try:
        return data[key]
    except (KeyError, ValueError, IndexError, AttributeError):
        return None


class KopiKananForwarder:
    def __init__(
        self,
        cancel_id: str,
        author_id: int,
        author_name: str,
        message: str = "",
        attachments: List[discord.Attachment] = [],
    ):
        self._cancel_id = cancel_id
        self._author_id = author_id
        self._author_name = author_name
        self._message = message or ""
        self._attachments = []
        for attach in attachments:
            self._attachments.append(attach.url)
        self._timestamp = datetime.now(tz=timezone.utc).timestamp()

        self._cancelled = False

    @property
    def cancel_id(self):
        return self._cancel_id

    @property
    def is_cancelled(self):
        return self._cancelled

    @property
    def author(self):
        return self._author_name

    @property
    def author_id(self):
        return self._author_id

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def message(self):
        return self._message or ""

    @property
    def attachments(self):
        return self._attachments

    def set_message(self, message: str):
        self._message = message
        if message == self._cancel_id:
            self._cancelled = True

    def set_timestamp(self, timestamp: int):
        self._timestamp = timestamp

    def add_attachment(self, attachment: Union[discord.Attachment, str]):
        if isinstance(attachment, str):
            self._attachments.append(attachment)
        elif isinstance(attachment, discord.Attachment):
            self._attachments.append(attachment.url)

    @classmethod
    def from_dict(cls, data: dict):
        timestamp = data["timestamp"]
        cancel_id = data["cancelId"]
        author_id = data["author"]
        author_name = data["authorName"]
        message = data["message"]
        attachments = data["attachments"]
        the_class = cls(cancel_id, int(author_id), author_name, message, attachments)
        the_class.set_timestamp(timestamp)
        return the_class

    def serialize(self):
        return {
            "timestamp": self._timestamp,
            "cancelId": self._cancel_id,
            "author": self._author_id,
            "authorName": self._author_name,
            "message": self._message,
            "attachments": self._attachments,
        }


class KopiKanan(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("cogs.KopiKanan")
        self._message = 864062785833664542
        self._target: discord.TextChannel = None
        self._message_real: discord.Message = None
        self._ONGOING: Dict[int, KopiKananForwarder] = {}

        self._prepare_kopikanan_handler.start()

    def cog_unload(self):
        self._prepare_kopikanan_handler.cancel()

    async def get_kopikanan(self, uuid: str):
        data = await self.bot.redis.get(f"potiakopikanan_{uuid}")
        if data is not None:
            return KopiKananForwarder.from_dict(data)
        return None

    async def set_kopikanan(self, kopikanan: KopiKananForwarder):
        await self.bot.redis.set(f"potiakopikanan_{kopikanan.author_id}", kopikanan.serialize())

    async def del_kopikanan(self, kopikanan: KopiKananForwarder):
        await self.bot.redis.rm(f"potiakopikanan_{kopikanan.author_id}")

    async def get_all_kopikanan(self):
        all_kopikanan = await self.bot.redis.getall("potiakopikanan_*")
        return [KopiKananForwarder.from_dict(data) for data in all_kopikanan]

    async def _send_ihateanime(self, to_be_sent: str):
        current = str(datetime.now(tz=timezone.utc).timestamp())
        filename = f"LaporanKopiKananMuseID_{current}.txt"

        return await self.bot.upload_ihateanime(to_be_sent, filename)

    @tasks.loop(seconds=1, count=1)
    async def _prepare_kopikanan_handler(self):
        self._target: discord.TextChannel = self.bot.get_channel(864044945031823360)
        the_channel: discord.TextChannel = self.bot.get_channel(864019453250633729)
        the_message = the_channel.get_partial_message(self._message)

        embed = discord.Embed()
        description = "Anda menemukan video yang melanggar hak cipta Muse Indonesia?"
        description += '\nAyo laporkan segera dengan mengeklik reaction "⚠"'
        description += "\nAnda akan mendapatkan pesan dari bot <@864027281923506176> untuk "
        description += "langkah selanjutnya!\n\n"
        description += "Pastikan Anda bisa menerima pesan dari bot <@864027281923506176>!\n"
        description += 'Aktifkan "Allow direct messages from server members." di `Privacy Settings`'
        embed.description = description

        await the_message.edit(embed=embed)
        fetch_msg: discord.Message = await the_message.fetch()

        any_warn_reaction = False
        for reaksi in fetch_msg.reactions:
            if "⚠" in str(reaksi):
                any_warn_reaction = True
                break
        if not any_warn_reaction:
            await fetch_msg.clear_reactions()
            await fetch_msg.add_reaction("⚠")
        self._message_real = fetch_msg

        all_kopikanan = await self.get_all_kopikanan()
        for kopikanan in all_kopikanan:
            self._ONGOING[kopikanan.author_id] = kopikanan

    @_prepare_kopikanan_handler.before_loop
    async def _before_prepare_kopikanan(self):
        await self.bot.wait_until_ready()

    async def _try_send_message(self, member: discord.Member):
        dm_channel: discord.DMChannel = member.dm_channel
        if dm_channel is None:
            self.logger.info(f"creating DM channel for kopikanan {member}")
            dm_channel = await member.create_dm()

        processing_data = self._ONGOING.get(member.id)
        if processing_data is None:
            self.logger.warning(f"{member} kopikanan is missing, ignoreing...")
            return
        close_id = processing_data.cancel_id
        message_start = "Halo! Jika Anda sudah menerima pesan ini, Potia akan membantu Anda dalam "
        message_start += "proses melapor oknum pelanggar hak cipta Muse Indonesia!\nAnda dapat membatalkan "
        message_start += f"proses ini dengan menulis: `{close_id}`\n\n"
        message_start += "Cukup tulis informasi di chat ini dengan link yang membantu, "
        message_start += "nanti Potia akan mengkonfirmasi dulu sebelum akan "
        message_start += "diteruskan ke Admin Muse Indonesia!"
        try:
            self.logger.info(f"{member} sending DM...")
            await dm_channel.send(message_start)
        except (discord.Forbidden, discord.HTTPException):
            self.logger.warning(f"{member} failed to send DM, ignoring...")

    async def _forward_copyright_report(self, member_id: int):
        processing_data = self._ONGOING.get(member_id)
        if processing_data is None:
            return

        content = processing_data.message
        attachments_url = processing_data.attachments
        author_name = processing_data.author
        parse_gambar = []
        for n, gambar in enumerate(attachments_url, 1):
            parse_gambar.append(f"[Gambar {n}]({gambar})")

        if parse_gambar:
            content += "\n\n" + " \| ".join(parse_gambar)  # noqa: W605

        if len(content) > 1950:
            iha_id = await self._send_ihateanime(content)
            real_content = "Dikarenakan teks yang dikirim lumayan banyak, <@864027281923506176> telah"
            real_content += f" mengunggah isi laporannya ke link berikut: <{iha_id}>\n"
            real_content += "Link tersebut valid selama kurang lebih 2.5 bulan."
        else:
            real_content = content

        real_timestamp = datetime.fromtimestamp(processing_data.timestamp, tz=timezone.utc)
        embed = discord.Embed(title="Laporan baru!", timestamp=real_timestamp, color=discord.Color.random())
        embed.set_thumbnail(url="https://p.ihateani.me/mjipsoqd.png")
        if attachments_url:
            first_image = attachments_url[0]
            embed.set_image(url=first_image)
        embed.description = real_content
        embed.set_author(name=author_name)

        await self._target.send(embed=embed)

    @commands.Cog.listener("on_raw_reaction_add")
    async def reaction_kopikanan_start(self, payload: RawReactionActionEvent):
        if payload.event_type != "REACTION_ADD":
            return

        if payload.message_id != self._message:
            return
        the_member: discord.Member = payload.member
        the_emoji = str(payload.emoji)
        if "⚠" in the_emoji and not the_member.bot:
            member_id = the_member.id
            is_ongoing = self._ONGOING.get(member_id)
            if is_ongoing is None:
                closing_data = f"batalc!{member_id}"
                forwarder = KopiKananForwarder(closing_data, member_id, str(the_member))
                self._ONGOING[member_id] = forwarder
                self.logger.info(f"Creating new kopikanan handler for {the_member}")
                await self.set_kopikanan(forwarder)
                self.logger.info(f"Sending message to the {the_member}")
                await self._try_send_message(the_member)
        if self._message_real is not None:
            try:
                await self._message_real.remove_reaction(the_emoji, the_member)
            except discord.HTTPException:
                pass

    @commands.Cog.listener("on_message")
    async def kopikanan_interceptor(self, message: discord.Message):
        if not isinstance(message.channel, discord.DMChannel):
            return

        if message.author.bot:
            return

        user_id = message.author.id
        kopikanan_frw = self._ONGOING.get(user_id)
        if kopikanan_frw is None:
            return

        kopikanan_frw.set_message(message.content)
        if kopikanan_frw.is_cancelled:
            await message.channel.send("Dibatalkan!")
            del self._ONGOING[user_id]
            await self.del_kopikanan(kopikanan_frw)
            return
        self._ONGOING[user_id] = kopikanan_frw
        for attach in message.attachments:
            kopikanan_frw.add_attachment(attach)

        confirming = await confirmation_dialog(
            self.bot, message, "Apakah anda yakin ingin mengirim ini?", message
        )
        if not confirming:
            await message.channel.send(
                "Baiklah, mohon tulis ulang kembali. Atau ketik "
                f"`{kopikanan_frw.cancel_id}` untuk membatalkannya"
            )
            return

        await self._forward_copyright_report(user_id)
        await message.channel.send("Laporan telah diteruskan! Terima kasih atas laporannya!")
        del self._ONGOING[user_id]
        await self.del_kopikanan()

    @commands.command(name="ceklaporan")
    @commands.is_owner()
    async def cek_laporan_yang_ada(self, ctx: commands.Context):
        all_message_id = list(self._ONGOING.keys())
        total = len(all_message_id)

        await ctx.send(
            f"Terdapat {total} laporan yang masih aktif dijalankan." + "\n" + "\n - ".join(all_message_id)
        )


def setup(bot: PotiaBot):
    bot.add_cog(KopiKanan(bot))
