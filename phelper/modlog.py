from datetime import datetime, timezone
from enum import Enum
from typing import Optional

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
    MEMBER_TIMED_BAN = 8
    MEMBER_UNBAN_TIMED = 9
    MEMBER_TIMEOUT = 10
    MEMBER_UNTIMEOUT = 11
    CHANNEL_CREATE = 20
    CHANNEL_UPDATE = 21
    CHANNEL_DELETE = 22
    MESSAGE_EDIT = 30
    MESSAGE_DELETE = 31
    MESSAGE_DELETE_BULK = 32
    EVASION_BAN = 40
    EVASION_TIMEOUT = 41


class PotiaModLog:
    def __init__(
        self, action: PotiaModLogAction, message: str = "", embed: discord.Embed = None, timestamp: int = None
    ) -> None:
        self._action = action
        self._message = message
        self._embed = embed
        self._timestamp = timestamp

    @property
    def action(self) -> PotiaModLogAction:
        return self._action

    @property
    def timestamp(self) -> Optional[int]:
        return getattr(self, "_timestamp", None)

    @property
    def message(self) -> str:
        return getattr(self, "_message", "")

    @property
    def embed(self) -> Optional[discord.Embed]:
        return getattr(self, "_embed", None)

    @action.setter
    def action(self, action: PotiaModLogAction):
        if isinstance(action, PotiaModLogAction):
            self._action = action

    @message.setter
    def message(self, message: str):
        if isinstance(message, str) and len(message.strip()) > 0:
            self._message = message

    @timestamp.setter
    def timestamp(self, timestamp: int = None):
        if isinstance(timestamp, int):
            self._timestamp = timestamp
        else:
            self._timestamp = datetime.now(timezone.utc).timestamp()

    @embed.setter
    def embed(self, embed: discord.Embed):
        if isinstance(embed, discord.Embed):
            self._embed = embed
