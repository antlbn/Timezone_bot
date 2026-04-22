from dataclasses import dataclass

@dataclass(frozen=True)
class TelegramConfig:
    delete_delay: int = 20
