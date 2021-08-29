import asyncio
import logging
from datetime import datetime, timezone
from typing import List, NamedTuple, Optional, Tuple, TypeVar, Union

import discord
from discord.ext import commands, tasks
from phelper.bot import PotiaBot

EMBED_MESSAGE = """<@&880773390305206274> <@&880773390305206275> <@&880773390305206276>

Halo semuanya! Jika kalian ingin menyampaikan keluhan atau kritik-saran untuk peladen (server) ini, kalian bisa mengeklik reaction (📫) yang tersedia di embed berikut. Dimohon sekali untuk tidak DM atau mention role `Muse ID`. Jika kalian melanggar, akan kami beri teguran langsung berupa Muted selama satu hari.

Jika anda tidak menerima pesan dari Bot, maka ada kesalahan dan mohon gunakan <#881163159833047060> untuk bantuan lebih lanjut.

Pastikan `Allow direct messages from server members.` aktif pada menu `Privacy Settings` peladen ini.

Kanal <#864019566048444447> bisa dipakai untuk kritik dan saran ke Muse Indonesia secara umum.
Terima kasih atas perhatiannya, selamat bergabung, dan mohon kerja samanya, ya!
"""  # noqa: E501


class ModMailAttachment:
    def __init__(self, url: str, filename: str, ctype: Optional[str] = None):
        self.url = url
        self.filename = filename
        self._type = ctype

    @property
    def type(self):
        return self._type or ""

    @classmethod
    def from_dict(cls, data: dict):
        return cls(data["url"], data["filename"], data["type"])

    @classmethod
    def from_attachment(cls, data: discord.Attachment):
        return cls(data.url, data.filename, data.content_type)

    @classmethod
    def from_sticker(cls, data: discord.StickerItem):
        return cls(data.url, f"Stiker: {data.name}", data.format.name)

    def serialize(self):
        return {"url": self.url, "filename": self.filename, "type": self._type}


class ModMailUser:
    def __init__(self, id: int, name: str, discriminator: str, avatar: str):
        self.id = id
        self.name = name
        self.discriminator = discriminator
        self.avatar = avatar

    def __str__(self):
        return f"{self.name}#{self.discriminator}"

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data["id"], name=data["username"], discriminator=data["discriminator"], avatar=data["avatar"]
        )

    @classmethod
    def from_user(cls, member: Union[discord.Member, discord.User]):
        return cls(
            id=member.id,
            name=member.name,
            discriminator=member.discriminator,
            avatar=member.avatar.with_format("png").url,
        )

    def serialize(self):
        return {
            "id": self.id,
            "username": self.name,
            "discriminator": self.discriminator,
            "avatar": self.avatar,
        }


class ModMailMessage:
    def __init__(
        self,
        author: ModMailUser,
        content: str,
        attachments: List[ModMailAttachment] = [],
        timestamp: int = None,
    ):
        self.author = author
        self.content = content
        self.attachments = attachments
        self.timestamp = timestamp or datetime.now(tz=timezone.utc).timestamp()

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            author=ModMailUser.from_dict(data["author"]),
            content=data["content"],
            attachments=[ModMailAttachment.from_dict(attachment) for attachment in data["attachments"]],
            timestamp=data["timestamp"],
        )

    @classmethod
    def from_message(cls, data: discord.Message):
        content = data.clean_content
        author = ModMailUser.from_user(data.author)
        attachments = [ModMailAttachment.from_attachment(attachment) for attachment in data.attachments]
        stickers = data.stickers
        for sticker in stickers:
            attachments.append(ModMailAttachment.from_sticker(sticker))
        timestamp = data.created_at.timestamp()
        return cls(author=author, content=content, attachments=attachments, timestamp=timestamp)

    def serialize(self):
        return {
            "author": self.author.serialize(),
            "content": self.content,
            "attachments": [attachment.serialize() for attachment in self.attachments],
            "timestamp": self.timestamp,
        }


class ModMailChannel:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name

    @classmethod
    def from_dict(cls, data: dict):
        return cls(id=data["id"], name=data["name"])

    @classmethod
    def from_channel(cls, data: discord.TextChannel):
        return cls(id=data.id, name=data.name)

    def serialize(self):
        return {"id": self.id, "name": self.name}


ModMailTarget = TypeVar("ModMailTarget", ModMailUser, ModMailChannel)


class ModMailForwarder(NamedTuple):
    message: ModMailMessage
    target: ModMailTarget
    raw_message: discord.Message


class ModMailHandler:
    def __init__(
        self,
        user: ModMailUser,
        channel: ModMailChannel,
        messages: List[ModMailMessage],
        timestamp: Optional[int] = None,
    ):
        self._user = user
        self._channel = channel
        self._messages = messages
        self._timestamp = timestamp or datetime.now(tz=timezone.utc).timestamp()
        self._on_hold = False

    def __iter__(self):
        for message in self._messages:
            yield message

    @property
    def id(self) -> int:
        return self._user.id

    @property
    def user(self) -> ModMailUser:
        return self._user

    @property
    def channel(self) -> ModMailChannel:
        return self._channel

    @channel.setter
    def channel(self, value: ModMailChannel):
        self._channel = value

    @property
    def messages(self) -> List[ModMailMessage]:
        return self._messages

    @property
    def timestamp(self):
        return self._timestamp

    def add_message(self, message: ModMailMessage):
        self._messages.append(message)

    def set_hold(self):
        self._on_hold = True

    def set_unhold(self):
        self._on_hold = False

    @property
    def is_on_hold(self):
        return self._on_hold

    @classmethod
    def from_dict(cls, data: dict):
        base = cls(
            user=ModMailUser.from_dict(data["user"]),
            messages=[ModMailMessage.from_dict(message) for message in data["messages"]],
            channel=ModMailChannel.from_dict(data["channel"]),
            timestamp=data["timestamp"],
        )
        if data["is_hold"]:
            base.set_hold()
        return base

    def serialize(self):
        return {
            "user": self._user.serialize(),
            "messages": [message.serialize() for message in self._messages],
            "channel": self._channel.serialize(),
            "timestamp": self._timestamp,
            "is_hold": self._on_hold,
        }

    def is_valid(self, target_id: int):
        return self._user.id == target_id or self._channel.id == target_id


class ModMail(commands.Cog):
    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("ModMail")
        self.db = bot.redis

        self._guild: discord.Guild = None
        self._channel: discord.TextChannel = None
        self._category: discord.CategoryChannel = None
        self._message: discord.Message = None
        self._log_channel: discord.TextChannel = None

        self._manager: List[ModMailHandler] = []

        self._mod_queue = asyncio.Queue()
        self._mod_done_queue = asyncio.Queue()
        self._mod_start_queue = asyncio.Queue()

        self._mod_send_task = asyncio.Task(self._modmail_forwareder_task())
        self._mod_start_task = asyncio.Task(self._modmail_start_task())
        self._mod_done_task = asyncio.Task(self._modmail_finished_task())

        self._is_ready = False
        self._initialize_modmail.start()

    def cog_unload(self):
        self._initialize_modmail.cancel()
        self._mod_send_task.cancel()
        self._mod_start_task.cancel()
        self._mod_done_task.cancel()

    def _find_manager(
        self, author: discord.User = None, channel: discord.TextChannel = None
    ) -> Tuple[Optional[ModMailHandler], bool]:
        if author is None and channel is None:
            return None, False
        for manager in self._manager:
            if author is not None and manager.is_valid(author.id):
                return manager, False
            elif channel is not None and manager.is_valid(channel.id):
                return manager, True
        return None, False

    async def _update_manager(self, manager: ModMailHandler):
        indx = -1
        for i, m in enumerate(self._manager):
            if m.id == manager.id:
                indx = i
                break
        if indx == -1:
            self._manager.append(manager)
        else:
            self._manager[indx] = manager
        await self.db.set(f"potiamodmail_{manager.id}", manager.serialize())

    async def _delete_manager(self, manager: ModMailHandler):
        indx = -1
        for i, m in enumerate(self._manager):
            if m.id == manager.id:
                indx = i
                break
        if indx >= 0:
            del self._manager[indx]
        await self.db.rm(f"potiamodmail_{manager.id}")

    async def _actually_forward_message(self, forward: ModMailForwarder):
        channel_target: Union[discord.DMChannel, discord.TextChannel] = None
        if isinstance(forward.target, ModMailUser):
            self.logger.info(f"Will be sending to user: {forward.target.id}")
            user_target = self.bot.get_user(forward.target.id)
            if user_target is None:
                return
            channel_check = user_target.dm_channel
            if channel_check is None:
                channel_check = await user_target.create_dm()
            channel_target = channel_check
        else:
            self.logger.info(f"Will be sending to channel: {forward.target.id}")
            channel_check = self._guild.get_channel(forward.target.id)
            if not isinstance(channel_check, discord.TextChannel):
                return
            channel_target = channel_check

        main_msg = forward.message
        the_timestamp = datetime.fromtimestamp(main_msg.timestamp, tz=timezone.utc)
        embed = discord.Embed(
            title="Pesan diterima", timestamp=the_timestamp, colour=discord.Color.dark_orange()
        )
        author = forward.message.author
        cut_name = author.name
        if len(cut_name) >= 250:
            cut_name = cut_name[:238] + "..."
        embed.set_author(name=f"{cut_name}#{author.discriminator}", icon_url=author.avatar)
        embed.description = main_msg.content
        if main_msg.attachments:
            an_image: str = None
            all_attach = []
            for attch in main_msg.attachments:
                if attch.type.startswith("image/") and an_image is None:
                    an_image = attch.url
                all_attach.append(f"[{attch.filename}]({attch.url})")
            if an_image is not None:
                embed.set_image(url=an_image)
            if all_attach:
                embed.add_field(name="Lampiran", value="\n".join(all_attach))

        embed.set_footer(text="📬 Muse Indonesia", icon_url=self._guild.icon)
        await channel_target.send(embed=embed)

        raw_receiver = forward.raw_message.channel
        embed_dict = embed.to_dict()
        embed_dict["title"] = "Pesan dikirim"
        embed_dict["color"] = discord.Color.dark_green().value
        await raw_receiver.send(embed=discord.Embed.from_dict(embed_dict))

    async def _modmail_forwareder_task(self):
        while not self._is_ready:
            await asyncio.sleep(0.2)
        self.logger.info("Starting modmail forwarder task...")
        while True:
            try:
                message: ModMailForwarder = await self._mod_queue.get()
                try:
                    await self._actually_forward_message(message)
                except Exception as e:
                    self.logger.error(f"Failed to execute modmail-forwarder: {e}")
                    self.bot.echo_error(e)
                self._mod_queue.task_done()
            except asyncio.CancelledError:
                break
        self.logger.info("Finished modmail forwarder task...")

    async def _upload_modmail_content(
        self, author: ModMailUser, messages: List[ModMailMessage], timestamp: int
    ):
        full_context = []
        prepend_context = ["=== Informasi Tiket ==="]
        prepend_context.append(f"Dibuka oleh: {author} ({author.id})")
        prepend_context.append(f"Pada (UNIX): {timestamp}")
        prepend_context.append("=== END OF INFORMATION LINE ===")
        full_context.append(prepend_context)
        if len(messages) < 1:
            full_context.append(["*Tidak ada pesan yang ditukar!*"])
        for pos, message in enumerate(messages, 1):
            content_inner = [f">> Pesan #{pos} <<"]
            content_inner.append(f"Dikirim oleh: {message.author} ({message.author.id})")
            content_inner.append("")
            content_inner.append(message.content)
            content_inner.append("")
            content_inner.append("Lampiran File:")
            if message.attachments:
                for n, attch in enumerate(message.attachments, 1):
                    content_inner.append(f"#{n}: {attch.filename} - {attch.url} ({attch.type})")
            else:
                content_inner.append("*Tidak ada lampiran untuk pesan ini*")
            full_context.append(content_inner)

        complete_message = ""
        for ctx in full_context:
            complete_message += "\n".join(ctx) + "\n\n"
        complete_message = complete_message.rstrip()
        current = str(self.bot.now().timestamp())
        filename = f"ModMailMuseID_{current}_{author}.txt"
        return await self.bot.upload_ihateanime(complete_message, filename)

    async def _actually_finish_modmail_task(self, handler: ModMailHandler):
        user = handler.user
        user_data = self.bot.get_user(user.id)
        if user_data is None:
            return
        dm_channel = user_data.dm_channel
        if dm_channel is None:
            dm_channel = await user_data.create_dm()

        channel_data = self._guild.get_channel(handler.channel.id)
        if channel_data is None:
            return

        embed = discord.Embed(
            title="Tiket ditutup",
            description="Terima kasih sudah menggunakan fitur modmail kami!",
            colour=discord.Color.dark_orange(),
            timestamp=self.bot.now(),
        )
        name_cut = user.name
        if len(user.name) >= 250:
            name_cut = user.name[:238] + "..."
        embed.set_footer(text="📬 Muse Indonesia", icon_url=self._guild.icon)
        await self._delete_manager(handler)
        await dm_channel.send(embed=embed)
        iha_url = await self._upload_modmail_content(user, handler.messages, handler.timestamp)
        self.logger.info(f"logged url: {iha_url}")
        desc_log = "Berikut adalah log semua pesan yang dikirim:"
        desc_log += f"\n{iha_url}"
        desc_log += "\n\nLink tersebut valid untuk 2.5 bulan sebelum dihapus selamanya!"
        embed.description = desc_log
        embed.set_footer(text=f"{name_cut}#{user.discriminator}", icon_url=user.avatar)
        await self._log_channel.send(embed=embed)
        await channel_data.delete(reason="Ticket closed")

    async def _modmail_finished_task(self):
        while not self._is_ready:
            await asyncio.sleep(0.2)
        self.logger.info("Starting modmail finished task...")
        while True:
            try:
                handler: ModMailHandler = await self._mod_done_queue.get()
                self.logger.info("Received modmail finished task...")
                try:
                    await self._actually_finish_modmail_task(handler)
                except Exception as e:
                    self.logger.error(f"Failed to execute modmail-finished: {e}")
                    self.bot.echo_error(e)
                self.logger.info("Modmail-finished are executed!")
                self._mod_done_queue.task_done()
            except asyncio.CancelledError:
                break
        self.logger.info("Finished modmail finished task...")

    async def _actually_start_modmail_task(self, handler: ModMailHandler):
        find_manager, _ = self._find_manager(handler.user)
        if find_manager is not None:
            return

        text_chan_name = f"📬-mail-{handler.user.id}"
        text_channel = await self._category.create_text_channel(name=text_chan_name)
        handler.channel = ModMailChannel.from_channel(text_channel)

        user = handler.user
        user_data = self.bot.get_user(user.id)
        if user_data is None:
            return
        dm_channel = user_data.dm_channel
        if dm_channel is None:
            dm_channel = await user_data.create_dm()

        ts_start = datetime.fromtimestamp(handler.timestamp, tz=timezone.utc)
        embed = discord.Embed(
            title="Modmail dibuka!", timestamp=ts_start, colour=discord.Color.dark_magenta()
        )
        desc = f"Modmail baru telah dibuka oleh **{user.name}#{user.discriminator}**"
        desc += "\nUntuk menutup modmailnya, cukup ketik `=tutup`"
        desc += f"\nTiket/Mod mail dibuat pada <t:{int(handler.timestamp)}>"
        embed.description = desc
        embed.set_footer(text="📬 Muse Indonesia", icon_url=self._guild.icon)

        await text_channel.send(
            content=f"Mod mail baru oleh **{user.name}#{user.discriminator}**",
            embed=embed,
        )
        await dm_channel.send(
            content="Silakan mulai mengetik, pesan anda akan diteruskan otomatis!", embed=embed
        )
        await self._update_manager(handler)

        log_embed = discord.Embed(title="Tiket baru", timestamp=ts_start, colour=discord.Colour.dark_green())
        log_embed.description = f"Gunakan kanal <#{text_channel.id}> untuk berbicara dengan user."
        name_cut = user.name
        if len(user.name) >= 250:
            name_cut = user.name[:238] + "..."
        log_embed.set_footer(text=f"{name_cut}#{user.discriminator}", icon_url=user.avatar)
        await self._log_channel.send(embed=log_embed)

    async def _modmail_start_task(self):
        while not self._is_ready:
            await asyncio.sleep(0.2)
        self.logger.info("Starting modmail start task...")
        while True:
            try:
                handler: ModMailHandler = await self._mod_start_queue.get()
                self.logger.info("Received modmail start task...")
                try:
                    await self._actually_start_modmail_task(handler)
                except Exception as e:
                    self.logger.error(f"Failed to execute modmail-start: {e}")
                    self.bot.echo_error(e)
                self.logger.info("Modmail-start are executed!")
                self._mod_start_queue.task_done()
            except asyncio.CancelledError:
                break
        self.logger.info("Finished modmail start task...")

    @tasks.loop(seconds=1.0, count=1)
    async def _initialize_modmail(self):
        self.logger.info("Initializing modmail...")
        self._guild = self.bot.get_guild(864004899783180308)
        self._category = self._guild.get_channel(881169284838088745)
        self._channel = self._guild.get_channel(881169412705624074)
        self._log_channel = self._guild.get_channel(881164519429246996)
        self._message = await self._channel.fetch_message(881169665664098334)

        embed = discord.Embed()
        embed.description = EMBED_MESSAGE

        await self._message.edit(embed=embed)
        any_mail_reaction = False
        for reaksi in self._message.reactions:
            if reaksi.emoji == "📬":
                any_mail_reaction = True
                break
        if not any_mail_reaction:
            await self._message.clear_reactions()
            await self._message.add_reaction("📬")

        _backlogged_modmail: List[ModMailHandler] = []
        _backlogged_modmail_redis = await self.db.getall("potiamodmail_*")
        for backlog in _backlogged_modmail_redis:
            _backlogged_modmail.append(ModMailHandler.from_dict(backlog))

        for backlog in _backlogged_modmail:
            self.logger.info(f"Restoring modmail from redis: {backlog.user.name}")
            self._manager[backlog.id] = backlog
        self._is_ready = True

    @_initialize_modmail.before_loop
    async def _initialize_modmail_before_loop(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener("on_message")
    async def _modmail_register_message(self, message: discord.Message):
        author = message.author
        if author.bot:
            return
        manager, _ = self._find_manager(author, message.channel)
        if manager is None:
            return
        if manager.is_on_hold:
            return

        clean_content = message.clean_content
        if clean_content.lower().startswith("p/"):
            return
        if clean_content.lower().startswith("=tutup"):
            manager.set_hold()
            await self._update_manager(manager)
            await self._mod_done_queue.put(manager)
            return
        if len(clean_content) >= 2000:
            await message.channel.send(content="Pesan anda terlalu panjang, mohon dikurangi!")
            return

        parsed_message = ModMailMessage.from_message(message)
        if message.channel.id == manager.channel.id:
            channel_target = manager.user
        else:
            channel_target = manager.channel
        self.logger.info(f"Will be forwarding to {channel_target}")
        manager.add_message(parsed_message)
        await self._update_manager(manager)
        await self._mod_queue.put(ModMailForwarder(parsed_message, channel_target, message))

    @commands.Cog.listener("on_raw_reaction_add")
    async def _modmail_reaction_handling(self, payload: discord.RawReactionActionEvent):
        if payload.event_type != "REACTION_ADD":
            return

        if payload.message_id != self._message.id:
            return
        the_member: discord.Member = payload.member
        the_emoji = str(payload.emoji)
        if "📬" in the_emoji and not the_member.bot:
            exist_manager, _ = self._find_manager(the_member, None)
            if exist_manager is None:
                self.logger.info(f"Initializing new modmail: {the_member}")
                startup = ModMailHandler(
                    ModMailUser.from_user(the_member),
                    None,
                    [],
                )
                await self._mod_start_queue.put(startup)
        if self._message is not None:
            try:
                await self._message.remove_reaction(the_emoji, the_member)
            except discord.HTTPException:
                pass


def setup(bot: PotiaBot):
    bot.add_cog(ModMail(bot))
