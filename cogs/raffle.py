import asyncio
import random
from typing import Dict, List, NamedTuple, Optional, Union

import discord
from discord.ext import commands, tasks
from phelper.bot import PotiaBot


class RaffleEntry:
    def __init__(self, id: int, name: str, number: Optional[int] = None):
        self._id = id
        self._name = name
        self._number = number

    def __eq__(self, other: Union[int, "RaffleEntry"]):
        if isinstance(other, int):
            return self.id == other
        elif isinstance(other, RaffleEntry):
            return self.id == other.id
        return False

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def number(self):
        return self._number

    @classmethod
    def from_user(cls, user: Union[discord.User, discord.Member]):
        return cls(user.id, user.name, 0)

    def set_number(self, number: int):
        if not isinstance(number, int):
            raise TypeError("Number must be an integer.")

        self._number = number

    @classmethod
    def from_dict(cls, data: dict):
        return cls(data["id"], data["name"], data["number"])

    def to_dict(self):
        return {"id": self.id, "name": self.name, "number": self.number}


class RaffleMeta:
    def __init__(self, item: str, channel: int, message: int, host: RaffleEntry):
        self._item = item
        self._channel = channel
        self._message = message
        self._host = host

    @property
    def id(self):
        return self._message

    @property
    def channel(self):
        return self._channel

    @property
    def host(self):
        return self._host

    @host.setter
    def host(self, host: RaffleEntry):
        self._host = host

    @property
    def item(self):
        return self._item

    @item.setter
    def item(self, item: str):
        self._item = item

    @classmethod
    def from_dict(cls, data: dict):
        return cls(data["item"], data["channel"], data["message"], RaffleEntry.from_dict(data["host"]))

    @classmethod
    def from_message(cls, message: discord.Message):
        clean_content = message.clean_content
        channel = message.channel.id
        message_id = message.id
        host = RaffleEntry.from_user(message.author)
        return cls(clean_content, channel, message_id, host)

    def to_dict(self):
        return {"item": self.item, "channel": self.channel, "message": self.id, "host": self.host.to_dict()}


class Raffle:
    def __init__(self, meta: RaffleMeta, entries: List[RaffleEntry] = []):
        self._meta = meta
        self._entries = entries or []
        self._raffled = False

    def __eq__(self, other: Union[int, "Raffle"]):
        if isinstance(other, int):
            return self.id == other
        elif isinstance(other, Raffle):
            return self.id == other.id
        return False

    def __contains__(self, other: Union[int, "Raffle"]):
        return other in self._entries

    @property
    def entries(self):
        return self._entries

    @property
    def item(self):
        return self._meta.item

    @item.setter
    def item(self, item: str):
        self._meta.item = item

    @property
    def id(self):
        return self._meta.channel

    @property
    def meta(self):
        return self._meta

    @property
    def host(self):
        return self._meta.host

    @host.setter
    def host(self, data: RaffleEntry):
        if not isinstance(data, RaffleEntry):
            return
        self._meta.host = data

    @property
    def jump_message(self):
        return f"https://discord.com/channels/864004899783180308/{self._meta.channel}/{self._meta.id}"

    def _get_numbers(self):
        return [entry.number for entry in self.entries]

    def add_entry(self, entry: RaffleEntry):
        if entry in self._entries:
            return
        if entry.number in self._get_numbers():
            raise ValueError("Number already taken.")
        self._entries.append(entry)

    def number_exist(self, entry: RaffleEntry):
        if entry.number in self._get_numbers():
            return False
        return True

    def remove_entry(self, entry: RaffleEntry):
        if entry not in self._entries:
            return
        self._entries.remove(entry)

    @property
    def raffled(self):
        return self._raffled

    def set_done(self):
        self._raffled = True

    def set_undone(self):
        self._raffled = False

    @classmethod
    def from_dict(cls, data: dict):
        temp = cls(
            RaffleMeta.from_dict(data["meta"]),
            [RaffleEntry.from_dict(entry) for entry in data["entries"]],
        )
        return temp

    def to_dict(self):
        return {
            "meta": self._meta.to_dict(),
            "entries": [entry.to_dict() for entry in self.entries],
            "raffled": self._raffled,
        }


class RaffleQueue(NamedTuple):
    entry: RaffleEntry
    channel: discord.TextChannel
    reference: discord.Message


class RaffleSystem(commands.Cog):
    _VALID_ROLES = [
        880773390305206276,
        880773390305206275,
        864010032308027392,
    ]

    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self._ONGOING_RAFFLES: Dict[str, Raffle] = {}
        self._FINISHED_RAFFLES: Dict[str, Raffle] = {}

        self._raffle_queue = asyncio.Queue()
        self._raffle_task = asyncio.Task(self._raffle_joiner_task())

        self._startup_raffles.start()

    def cog_unload(self):
        self._startup_raffles.cancel()

    @tasks.loop(seconds=1.0, count=1)
    async def _startup_raffles(self):
        ongoing_raffles = await self.bot.redis.getall("potiaraffle_*")
        for raffles in ongoing_raffles:
            raffle = Raffle.from_dict(raffles)
            if raffle.raffled:
                self._FINISHED_RAFFLES[str(raffle.meta.id)] = raffle
            else:
                self._ONGOING_RAFFLES[str(raffle.id)] = raffle

    async def _real_raffle_task_process(self, queue: RaffleQueue):
        channel = queue.channel
        reference = queue.reference
        raffle_data = self._ONGOING_RAFFLES[str(channel.id)]
        raffle_data.add_entry(queue.entry)
        self._ONGOING_RAFFLES[str(channel.id)] = raffle_data

        await self.bot.redis.set(f"potiaraffle_{channel.id}_{reference.id}", raffle_data.to_dict())
        await channel.send("Nomor anda dimasukan ke undian!", reference=reference)

    async def _raffle_joiner_task(self):
        while True:
            try:
                new_task: RaffleQueue = await self._raffle_queue.get()
                try:
                    await self._real_raffle_task_process(new_task)
                except Exception:
                    pass
                self._raffle_queue.task_done()
            except asyncio.CancelledError:
                return

    def _member_valid_role(self, member: discord.Member):
        for valid in self._VALID_ROLES:
            if member.get_role(valid) is not None:
                return True
        return False

    @commands.Cog.listener("on_message")
    async def _listen_for_raffle_entry(self, message: discord.Message):
        channel = message.channel
        guild = message.guild
        if guild is None:
            return
        if str(channel.id) not in self._ONGOING_RAFFLES:
            return

        member = message.author
        if not self._member_valid_role(member):
            return

        member_id = member.id
        raffle = self._ONGOING_RAFFLES[str(channel.id)]
        if raffle.raffled:
            return
        if raffle.host.id == member_id:
            return
        content = message.clean_content
        if not content.isdigit() and member_id not in raffle:
            return await channel.send("Mohon berikan angka undian yang benar!", reference=message)

        if member_id in raffle:
            return await channel.send(f"Anda sudah ikut undian **{raffle.item}**!", reference=message)

        entry = RaffleEntry.from_user(member)
        entry.set_number(int(content))
        if raffle.number_exist(entry):
            return await channel.send("Nomor tersebut sudah diambil orang lain!", reference=message)

        await self._raffle_queue.put(RaffleQueue(entry, channel, message))

    @commands.command(name="undian")
    @commands.has_guild_permissions(administrator=True)
    async def _raffle_cmd(self, ctx: commands.Context, *, item: str):
        raffle_meta = RaffleMeta.from_message(ctx.message)
        raffle_meta.item = item

        raffle = Raffle(raffle_meta)
        if str(raffle.id) in self._ONGOING_RAFFLES:
            raffle_exist = self._ONGOING_RAFFLES[str(raffle.id)]
            if not raffle_exist.raffled:
                return await ctx.send(
                    "Sedang ada undian berlangsung di kanal ini, mohon hentikan terlebih dahulu dengan "
                    f"reply pesan {raffle_exist.jump_message} dengan `p/undi`"
                )
        self._ONGOING_RAFFLES[str(raffle.id)] = raffle
        await self.bot.redis.set(f"potiaraffle_{raffle.id}_{raffle.meta.id}", raffle.to_dict())
        await ctx.send(f"Undian untuk **{item}** dimulai, silakan ketik angka yang anda inginkan")

    @commands.command(name="undi")
    @commands.guild_only()
    async def _raffle_complete_cmd(self, ctx: commands.Context):
        message: discord.Message = ctx.message
        reference_msg = message.reference
        channel: discord.TextChannel = ctx.channel
        author = ctx.author
        if reference_msg is None:
            return await ctx.send("Mohon gunakan perintah dengan reply ke perintah `p/undian` dari anda!")

        raffle_data = None
        from_ongoing = False
        if str(channel.id) in self._ONGOING_RAFFLES:
            from_ongoing = True
            raffle_data = self._ONGOING_RAFFLES[str(channel.id)]
        if str(reference_msg.message_id) in self._FINISHED_RAFFLES:
            raffle_data = self._FINISHED_RAFFLES[str(reference_msg.message_id)]

        if raffle_data is None:
            return await ctx.send("Undian tidak dapat ditemukan!")

        if raffle_data.host.id != author.id:
            return await ctx.send("Anda bukanlah orang yang memulai undian tersebut!")

        entries = raffle_data.entries
        if len(entries) < 1:
            return await ctx.send("Tidak ada yang ikut undian ini!", reference=reference_msg)

        current_ts = int(self.bot.now().timestamp())
        random.seed(current_ts)
        if from_ongoing:
            raffle_data.set_done()
            del self._ONGOING_RAFFLES[str(channel.id)]
            self._FINISHED_RAFFLES[str(reference_msg.message_id)] = raffle_data
            await self.bot.redis.set(
                f"potiaraffle_{channel.id}_{reference_msg.message_id}", raffle_data.to_dict()
            )

        select_winner = random.choice(entries)
        await ctx.send(
            f"Selamat kepada <@{select_winner.id}>, anda mendapatkan **{raffle_data.item}**!"
            f"Nomor undian anda adalah: {select_winner.number}",
            reference=reference_msg,
        )


def setup(bot: PotiaBot):
    bot.add_cog(RaffleSystem(bot))
