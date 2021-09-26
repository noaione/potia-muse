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
import json


class Author(Enum):
    USER = 0
    BOT = 1


@dataclass
class Conversation:
    content: str
    author: Author


INITIATION_TEXT = """The following is a conversation between an AI and a human. The AI is smart, helpful, creative, clever, friendly, and sometimes loves to joke."""  # noqa

AI_CONFIGURATION = {
    "temperature": 0.9,
    "max_tokens": 150,
    "top_p": 1,
    "frequency_penalty": 0.4,
    "presence_penalty": 0.6,
}


class ActiveChat:
    def __init__(self, user: discord.Member, channel: discord.TextChannel, session: aiohttp.ClientSession):
        self.user = user
        self.channel = channel
        self.session = session
        self.logger = logging.getLogger(f"AIChat.{user.id}")
        self._chat_contents: List[Conversation] = []

    def _create_prompt(self, new_content: str = None):
        all_datas = [INITIATION_TEXT]
        for content in self._chat_contents:
            if content.author == Author.USER:
                all_datas.append(f"Human: {content.content}")
            elif content.author == Author.BOT:
                all_datas.append(f"AI: {content.content}")
        if new_content is not None:
            all_datas.append(f"Human: {new_content}")
            self._chat_contents.append(Conversation(new_content, Author.USER))
            all_datas.append("AI:")
        return "\n".join(all_datas)

    async def send(self, content: str = None):
        prompts = self._create_prompt(content)

        ALL_CONTENTS = AI_CONFIGURATION.copy()
        ALL_CONTENTS["prompt"] = prompts
        ALL_CONTENTS["stop"] = ["\n", " Human:", " AI:"]

        self.logger.debug(f"Requesting with promps: {json.dumps(prompts)}")
        async with self.session.post(
            "https://api.openai.com/v1/engines/davinci/completions", json=ALL_CONTENTS
        ) as resp:
            data = await resp.json()
            first_content: str = complex_walk(data, "choices.0.text")
            conversation = Conversation(first_content.strip(), Author.BOT)
            if content is None:
                # Append text to previous prompt.
                self._chat_contents[-1].content += f" {conversation.content}"
            else:
                self._chat_contents.append(conversation)
            return conversation


class DavinciAIChat(commands.Cog):
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
            "Ketik `lanjut` untuk membuat AI meneruskan teks sebelumnya!\n"
            "Jika tidak ada konversasi dalam 1 menit, chat akan berhenti otomatis.\n\n"
            "Dimohon gunakan bahasa Inggris."
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
                self.logger.info("Fetching responses...")
                ai_response = await ai_chat.send(new_prompt)
                if not ai_response.content:
                    await ctx.send("**Pesan dari Potia**: *AI tidak dapat menjawab pesan anda.*")
                else:
                    await ctx.send(ai_response.content, reference=last_known_msg)

            def check(msg: discord.Message):
                return msg.author == author and msg.channel == channel

            res: discord.Message

            try:
                res = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                stop_reason = "Timeout"
                break

            content = res.clean_content

            if content.lower() == "stop":
                stop_reason = "User sendiri"
                break

            if content.lower() in ["lanjut", "lanjutkan", "continue"]:
                self.logger.info("User aksed the AI to continue, continuing without new prompt for user.")
                new_prompt = None
            else:
                new_prompt = content
            last_known_msg = res

        await session.close()
        await ctx.send(f"Konversasi selesai, konversasi dihentikan karena {stop_reason}")


def setup(bot: PotiaBot):
    bot.add_cog(DavinciAIChat(bot))
