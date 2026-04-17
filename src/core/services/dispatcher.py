import logging
from src.core.domain.value_objects import InputData, MessageContext, PendingMessage
from src.core.domain.enums import Platform
from src.core.pipeline.pipeline import Pipeline
from src.ports.executor import CommandExecutorPort

logger = logging.getLogger(__name__)

class MessageDispatcher:
    def __init__(
        self,
        pipeline: Pipeline,
        tg_executor: CommandExecutorPort | None,
        dc_executor: CommandExecutorPort | None,
    ):
        self.pipeline = pipeline
        self.routes = {}
        if tg_executor:
            self.routes[Platform.TELEGRAM] = tg_executor
        if dc_executor:
            self.routes[Platform.DISCORD] = dc_executor

    async def process_input(self, data: InputData) -> None:
        """Processes raw InputData through the pipeline and dispatches commands."""
        ctx = MessageContext(input=data, from_pending=False)
        await self._run_and_dispatch(ctx, data.platform)

    async def process_pending(self, pending: PendingMessage) -> None:
        """Processes a frozen PendingMessage, skipping guard, aging, and detection (using cache)."""
        ctx = MessageContext(
            input=pending.original_input,
            from_pending=True,
            detection=pending.detection,
        )
        await self._run_and_dispatch(ctx, pending.original_input.platform)

    async def _run_and_dispatch(self, ctx: MessageContext, platform: Platform) -> None:
        ctx = await self.pipeline.run(ctx)
        commands = ctx.commands
        
        if not commands:
            return

        executor = self.routes.get(platform)
        if executor:
            await executor.execute(commands)
        else:
            logger.warning(f"No executor configured for platform {platform}")
