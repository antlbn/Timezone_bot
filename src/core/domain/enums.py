from enum import StrEnum

class Platform(StrEnum):
    TELEGRAM = "telegram"
    DISCORD = "discord"

class ResponseStyle(StrEnum):
    BLOCK = "block"
    INLINE = "inline"
