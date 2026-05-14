from typing import Any
from aiogram import Dispatcher, Router, BaseMiddleware
from aiogram.types import TelegramObject, Message

from core.services.message_processing import MessageProcessingService
from adapters.inbound.telegram.middlewares import ErrorHandlingMiddleware, DependencyMiddleware
from container import AppContainer
from adapters.inbound.telegram.config import TelegramConfig

def setup_dispatcher(
    dp: Dispatcher, 
    container: AppContainer, 
    tg_config: TelegramConfig
) -> None:
    dp.update.outer_middleware(ErrorHandlingMiddleware())
    dp.update.outer_middleware(DependencyMiddleware(container, tg_config))

    # Routers
    from adapters.inbound.telegram.commands_handler import router as tg_commands_router
    from adapters.inbound.telegram.onboarding_handler import router as onboarding_router
    from adapters.inbound.telegram.callbacks_handler import router as tg_callbacks_router
    from adapters.inbound.telegram.handlers import on_message as tg_on_message

    dp.include_router(tg_commands_router)
    dp.include_router(onboarding_router)
    dp.include_router(tg_callbacks_router)

    # General message handler (pipeline) must be LAST
    pipeline_router = Router(name="pipeline")
    
    @pipeline_router.message()
    async def wrapped_tg_on_message(message: Message, message_processor: MessageProcessingService):
        await tg_on_message(message, message_processor)
    
    dp.include_router(pipeline_router)
