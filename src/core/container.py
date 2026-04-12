from src.adapters.outbound.sqlite_storage import SQLiteStorage
from src.core.pipeline.pipeline import Pipeline
from src.adapters.executors.telegram_executor import TelegramCommandExecutor
from src.adapters.executors.discord_executor import DiscordCommandExecutor
from src.adapters.outbound.nominatim_geo import NominatimGeo

class AppContainer:
    def __init__(self, storage: SQLiteStorage, pipeline: Pipeline, tg_executor: TelegramCommandExecutor, dc_executor: DiscordCommandExecutor, geocoder: NominatimGeo):
        self.storage = storage
        self.pipeline = pipeline
        self.tg_executor = tg_executor
        self.dc_executor = dc_executor
        self.geocoder = geocoder
