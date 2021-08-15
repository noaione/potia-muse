import argparse
from typing import Dict, List, NamedTuple, Optional, Union

BotConfig = Dict[str, Union[str, int, bool, Dict[str, Union[str, int, bool]]]]


class ConfigParseError(Exception):
    def __init__(self, location: str, reason: str) -> None:
        self.location = location
        self.reason = reason
        text_data = "Terjadi kesalahan ketika memproses konfigurasi!\n"
        text_data += f"Posisi error: {location}\nAlasan: {reason}"
        super().__init__(text_data)


def str_or_none(value: Optional[str]) -> str:
    return value if value is not None else ""


class RedisConfig(NamedTuple):
    ip_hostname: str
    port: int
    password: Optional[str] = None

    @classmethod
    def parse_config(cls, config: BotConfig):
        ip_hostname = config.get("ip_hostname", None)
        if ip_hostname is None:
            raise ConfigParseError(
                "redisdb.ip_hostname", "Redis dibutuhkan untuk berbagai macam fitur naoTimes!"
            )
        port = config.get("port", 6379)
        password = config.get("password", None)
        return cls(ip_hostname, port, password)

    def serialize(self):
        return {
            "ip_hostname": self.ip_hostname,
            "port": self.port,
            "password": self.password,
        }


class PotiaArgParsed(NamedTuple):
    cogs_skip: List[str] = []

    @classmethod
    def parse_argparse(cls, parsed: argparse.Namespace):
        skipped_cogs = []
        for cogs in parsed.cogs_skip:
            if not cogs.startswith("cogs."):
                cogs = "cogs." + cogs
            skipped_cogs.append(cogs)
        return cls(skipped_cogs)


class PotiaBotConfig(NamedTuple):
    token: str
    default_prefix: str
    redis: RedisConfig
    init_config: PotiaArgParsed
    modlog_channel: Optional[int]
    twitter_key: Optional[str]

    @classmethod
    def parse_config(cls, config: BotConfig, parsed_ns: argparse.Namespace) -> "PotiaBotConfig":
        token = config.get("token", None)
        if token is None:
            raise ConfigParseError("token", "Missing token to start the bot!")
        default_prefix = config.get("prefix", "p/")
        redis_config = RedisConfig.parse_config(config.get("redisdb", {}))
        modlog_channel = config.get("modlog_channel", None)
        twitter_key = config.get("twitter", None)
        argparsed = PotiaArgParsed.parse_argparse(parsed_ns)

        return cls(
            token,
            default_prefix,
            redis_config,
            argparsed,
            modlog_channel,
            twitter_key,
        )

    def serialize(self):
        return {
            "token": self.token,
            "prefix": self.default_prefix,
            "redisdb": self.redis.serialize(),
            "modlog_channel": self.modlog_channel,
            "twitter": self.twitter_key,
        }
