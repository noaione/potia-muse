import argparse
from typing import Dict, List, NamedTuple, Optional, Union

import uuid
from discord.enums import VoiceRegion

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


class PotiaLavalinkSpotifyNode(NamedTuple):
    id: str
    secret: str
    url: str

    @classmethod
    def parse_config(cls, config: BotConfig):
        id = config.get("id", None)
        if id is None:
            raise ConfigParseError(
                "lavalink_nodes.X.spotify.id", "Spotify ID dibutuhkan untuk fitur Spotify!"
            )
        secret = config.get("secret", None)
        if secret is None:
            raise ConfigParseError(
                "lavalink_nodes.X.spotify.secret", "Spotify Secret dibutuhkan untuk fitur Spotify!"
            )
        url = config.get("url", None)
        return cls(id, secret, url)

    def serialize(self):
        return {"id": self.id, "secret": self.secret, "url": self.url}


class PotiaLavalinkNodes(NamedTuple):
    host: str
    port: int
    password: str
    identifier: str
    region: VoiceRegion
    spotify: Optional[PotiaLavalinkSpotifyNode]

    @property
    def rest_uri(self):
        return f"http://{self.host}:{self.port}"

    @classmethod
    def parse_config(cls, config: BotConfig):
        host = config.get("host", None)
        if host is None:
            raise ConfigParseError(
                "lavalink.host", "Lavalink dibutuhkan untuk berbagai macam fitur naoTimes!"
            )
        port = config.get("port", 2333)
        password = config.get("password", None)
        identifier = config.get("identifier", None)
        if identifier is None:
            idv4 = str(uuid.uuid4())
            identifier = f"potia-lava-{idv4}"
        region = config.get("region", None)
        if region is None:
            region = VoiceRegion.us_west
        else:
            region = VoiceRegion(region.replace("_", "-"))
        spotify_node = config.get("spotify", None)
        if spotify_node is not None:
            spotify_node = PotiaLavalinkSpotifyNode.parse_config(spotify_node)
        return cls(host, port, password, identifier, region, spotify_node)

    def serialize(self):
        base = {
            "host": self.host,
            "port": self.port,
            "password": self.password,
            "identifier": self.identifier,
            "region": self.region.value,
        }
        if self.spotify:
            base["spotify"] = self.spotify.serialize()


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
    lavanodes: List[PotiaLavalinkNodes]
    openai_token: Optional[str]

    @classmethod
    def parse_config(cls, config: BotConfig, parsed_ns: argparse.Namespace) -> "PotiaBotConfig":
        token = config.get("token", None)
        if token is None:
            raise ConfigParseError("token", "Missing token to start the bot!")
        default_prefix = config.get("prefix", "p/")
        redis_config = RedisConfig.parse_config(config.get("redisdb", {}))
        modlog_channel = config.get("modlog_channel", None)
        twitter_key = config.get("twitter", None)
        lavalinks_nodes = []
        for node in config.get("lavalink_nodes", []):
            lavalinks_nodes.append(PotiaLavalinkNodes.parse_config(node))
        openai_token = config.get("openai_token", None)
        argparsed = PotiaArgParsed.parse_argparse(parsed_ns)

        return cls(
            token,
            default_prefix,
            redis_config,
            argparsed,
            modlog_channel,
            twitter_key,
            lavalinks_nodes,
            openai_token,
        )

    def serialize(self):
        basis = {
            "token": self.token,
            "prefix": self.default_prefix,
            "redisdb": self.redis.serialize(),
            "modlog_channel": self.modlog_channel,
            "twitter": self.twitter_key,
            "lavalink_nodes": [node.serialize() for node in self.lavanodes],
            "openai_token": str_or_none(self.openai_token),
        }
        return basis
