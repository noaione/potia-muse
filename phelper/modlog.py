from datetime import datetime, timezone
from enum import Enum
from typing import NamedTuple

import discord


class PotiaModLogAction(Enum):
    MEMBER_JOIN = 0
    MEMBER_LEAVE = 1
    MEMBER_UPDATE = 2
    MEMBER_BAN = 3
    MEMBER_UNBAN = 4
    MEMBER_KICK = 5
    MEMBER_SHADOWBAN = 6
    MEMBER_UNSHADOWBAN = 7
    CHANNEL_CREATE = 10
    CHANNEL_UPDATE = 11
    CHANNEL_DELETE = 12
    MESSAGE_EDIT = 20
    MESSAGE_DELETE = 21
    MESSAGE_DELETE_BULK = 22


class PotiaModLog(NamedTuple):
    action: PotiaModLogAction
    message: str = ""
    embed: discord.Embed = None
    timestamp: int = None

    def set_timestamp(self, timestamp: int = None):
        if isinstance(timestamp, int):
            self.timestamp = timestamp
        else:
            self.timestamp = datetime.now(tz=timezone.utc).timestamp()

    def set_embed(self, embed: discord.Embed):
        if isinstance(embed, discord.Embed):
            self.embed = embed

    def set_message(self, message: str):
        if isinstance(message, str) and len(message.strip()) > 0:
            self.message = message

    def set_action(self, action: PotiaModLogAction):
        if isinstance(action, PotiaModLogAction):
            self.action = action
