import logging
from datetime import datetime, timezone
import aiohttp

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


class KopiKanan(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("cogs.KopiKanan")
        self._message = 864062785833664542
        self._target: discord.TextChannel = self.bot.get_channel(864044945031823360)
        self._message_real: discord.Message = None
        self._ongoing_process = {}

        self._prepare_kopikanan_handler.start()

    def cog_unload(self):
        self._prepare_kopikanan_handler.cancel()

    @staticmethod
    def current_timestamp():
        return datetime.now(tz=timezone.utc).timestamp()

    @staticmethod
    async def _send_ihateanime(to_be_sent: str):
        async with aiohttp.ClientSession() as session:
            current = str(datetime.now(tz=timezone.utc).timestamp())
            form_data = aiohttp.FormData()
            form_data.add_field(
                name="file",
                value=to_be_sent.encode("utf-8"),
                content_type="text/plain",
                filename=f"LaporanKopiKananMuseID_{current}.txt",
            )
            async with session.post("https://p.ihateani.me/upload", data=form_data) as resp:
                if resp.status == 200:
                    res = await resp.text()
                    return res

    @tasks.loop(seconds=1, count=1)
    async def _prepare_kopikanan_handler(self):
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

    async def _try_send_message(self, member: discord.Member):
        dm_channel: discord.DMChannel = member.dm_channel
        if dm_channel is None:
            dm_channel = await member.create_dm()

        member_id = str(member.id)
        processing_data = try_get(self._ongoing_process, member_id)
        if processing_data is None:
            return
        close_id = processing_data["cancelId"]
        message_start = "Halo! Jika Anda sudah menerima pesan ini, Potia akan membantu Anda dalam "
        message_start += "proses melapor oknum pelanggar hak cipta Muse Indonesia!\nAnda dapat membatalkan "
        message_start += f"proses ini dengan menulis: `{close_id}`\n\n"
        message_start += "Cukup tulis informasi di chat ini dengan link yang membantu, "
        message_start += "nanti Potia akan mengkonfirmasi dulu sebelum akan "
        message_start += "diteruskan ke Admin Muse Indonesia!"
        await dm_channel.send(message_start)

    async def _forward_copyright_report(self, member_id: str):
        processing_data = try_get(self._ongoing_process, member_id)
        if processing_data is None:
            return

        content = processing_data["message"]
        author_name = processing_data["authorName"]

        if len(content) > 1950:
            iha_id = await self._send_ihateanime(content)
            real_content = "Dikarenakan teks yang dikirim lumayan banyak, <@864027281923506176> telah"
            real_content += f" mengunggah isi laporannya ke link berikut: <{iha_id}>\n"
            real_content += "Link tersebut valid selama kurang lebih 2.5 bulan."
        else:
            real_content = content

        real_timestamp = datetime.fromtimestamp(processing_data["timestamp"], tz=timezone.utc)
        embed = discord.Embed(title="Laporan baru!", timestamp=real_timestamp, color=discord.Color.random())
        embed.set_thumbnail(url="https://p.ihateani.me/mjipsoqd.png")
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
            member_id = str(the_member.id)
            if member_id not in self._ongoing_process:
                closing_data = f"batalc!{member_id}"
                data_to_process = {
                    "timestamp": self.current_timestamp(),
                    "message": "",
                    "cancelId": closing_data,
                    "author": member_id,
                    "authorName": str(the_member),
                }
                self._ongoing_process[member_id] = data_to_process
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

        user_id = str(message.author.id)
        complex_data = try_get(self._ongoing_process, user_id)
        if complex_data is None:
            return

        cancelId = complex_data["cancelId"]
        if message.content == cancelId:
            await message.channel.send("Dibatalkan!")
            del self._ongoing_process[user_id]
            return
        complex_data["message"] = message.content
        self._ongoing_process[user_id] = complex_data

        confirming = await confirmation_dialog(
            self.bot, message, "Apakah anda yakin ingin mengirim ini?", message
        )
        if not confirming:
            await message.channel.send(
                "Baiklah, mohon tulis ulang kembali. Atau ketik "
                f"`{complex_data['cancelId']}` untuk membatalkannya"
            )
            return

        await self._forward_copyright_report(user_id)
        await message.channel.send("Laporan telah diteruskan! Terima kasih atas laporannya!")
        del self._ongoing_process[user_id]

    @commands.command(name="ceklaporan")
    @commands.is_owner()
    async def cek_laporan_yang_ada(self, ctx: commands.Context):
        all_message_id = list(self._ongoing_process.keys())
        total = len(all_message_id)

        await ctx.send(
            f"Terdapat {total} laporan yang masih aktif dijalankan." + "\n" + "\n - ".join(all_message_id)
        )


def setup(bot: PotiaBot):
    bot.add_cog(KopiKanan(bot))
