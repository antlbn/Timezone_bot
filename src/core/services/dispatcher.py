import logging
from src.core.domain.value_objects import InputData, MessageContext
from src.core.domain.enums import Platform
from src.core.pipeline.pipeline import Pipeline
from src.ports.command_bus import CommandBusPort

logger = logging.getLogger(__name__)

class MessageDispatcher:
    def __init__(
        self,
        pipeline: Pipeline,
        tg_executor: CommandBusPort | None,
        dc_executor: CommandBusPort | None,
    ):
        self.pipeline = pipeline
        self.routes = {}
        if tg_executor:
            self.routes[Platform.TELEGRAM] = tg_executor
        if dc_executor:
            self.routes[Platform.DISCORD] = dc_executor

    async def process_input(self, data: InputData, from_pending: bool = False) -> None:
        """Processes raw InputData through the pipeline and dispatches commands."""
        ctx = MessageContext(input=data, from_pending=from_pending)
        
        ctx = await self.pipeline.run(ctx)
        commands = ctx.commands
        
        if not commands:
            return

        executor = self.routes.get(data.platform)
        if executor:
            await executor.execute(commands)
        else:
            logger.warning(f"No executor configured for platform {data.platform}")
