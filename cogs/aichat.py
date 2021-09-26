import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List

import aiohttp
import discord
from discord.ext import commands
from phelper.bot import PotiaBot
from phelper.utils import complex_walk


class Author(Enum):
    USER = 0
    BOT = 1


@dataclass
class Conversation:
    content: str
    author: Author


INITIATION_TEXT = """The following is a conversation between an AI assistant and a human. The AI is smart, helpful, creative, clever, friendly, and sometimes loves to joke."""  # noqa

AI_CONFIGURATION = {
    "temperature": 0.9,
    "max_tokens": 150,
    "top_p": 1,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.6,
}


class ActiveChat:
    def __init__(self, user: discord.Member, channel: discord.TextChannel, session: aiohttp.ClientSession):
        self.user = user
        self.channel = channel
        self.session = session
        self._chat_contents: List[Conversation] = []

    def _create_prompt(self, new_content: str):
        all_datas = [INITIATION_TEXT]
        for content in self._chat_contents:
            if content.author == Author.USER:
                all_datas.append(f"Human: {content.content}")
            elif content.author == Author.BOT:
                all_datas.append(f"AI: {content.content}")
        all_datas.append(f"Human: {new_content}")
        self._chat_contents.append(Conversation(new_content, Author.USER))
        return "\n".join(all_datas)

    async def send(self, content: str):
        prompts = self._create_prompt(content)

        ALL_CONTENTS = AI_CONFIGURATION.copy()
        ALL_CONTENTS["prompt"] = prompts
        ALL_CONTENTS["stop"] = ["\n", " Human:", " AI:"]

        async with self.session.post(
            "https://api.openai.com/v1/engines/curie/completions", json=ALL_CONTENTS
        ) as resp:
            data = await resp.json()
            first_content = complex_walk(data, "choices.0.text")
            conversation = Conversation(first_content, Author.BOT)
            self._chat_contents.append(conversation)
            return conversation


class CurieAIChat(commands.Cog):
    """A GPT-3 powered chat engine using Curie model"""

    def __init__(self, bot: PotiaBot):
        self.bot = bot
        self.logger = logging.getLogger("Cog.AIChat")

    @commands.command(name="aichat")
    async def aichat(self, ctx: commands.Context, *, new_prompt: str):
        """A GPT-3 powered chat engine using Curie model"""

        if not self.bot.config.openai_token:
            return

        if not new_prompt:
            return await ctx.send("Mohon berikan teks sebagai tanda mulai!")

        await ctx.send(
            f"{ctx.author.mention} memulai konversasi dengan AI...\n"
            "Ketik `stop` jika sudah selesai!\n"
            "Jika tidak ada konversasi dalam 1 menit, chat akan berhenti otomatis."
        )

        channel = ctx.channel
        author = ctx.author

        self.logger.info(f"Initiating new conversation at: {channel} with {author}")

        session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.bot.config.openai_token}"})

        ai_chat = ActiveChat(author, channel, session)

        last_known_msg: discord.Message = ctx.message

        stop_reason = None
        while True:
            async with channel.typing():
                ai_response = await ai_chat.send(new_prompt)
                await ctx.send(ai_response.content, reference=last_known_msg)

            def check(msg: discord.Message):
                return msg.author == author and msg.channel == channel

            res: discord.Message
            user: discord.Member

            try:
                res, user = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                stop_reason = "Timeout"
                break

            if res.clean_content.lower() == "stop":
                stop_reason = "User sendiri"
                break

            last_known_msg = res
            new_prompt = res.clean_content

        await session.close()
        await ctx.send(f"Konversasi selesai, konversasi dihentikan karena {stop_reason}")


def setup(bot: PotiaBot):
    bot.add_cog(CurieAIChat(bot))
