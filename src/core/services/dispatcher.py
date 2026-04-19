import logging
from core.domain.value_objects import InputData, MessageContext, OnboardingPendingMessage
from core.domain.enums import Platform
from core.pipeline.pipeline import Pipeline
from ports.executor import CommandExecutorPort

logger = logging.getLogger(__name__)

class MessageDispatcher:
    """Routes messages through the appropriate pipeline and dispatches resulting commands.

    Two pipelines:
      fresh_pipeline  — for new inbound messages
                        (Guard → Aging → Detection → GeoResolve → Registration
                         → Hydration → Chillout → Format → Command)
      replay_pipeline — for onboarding-pending messages after onboarding
                        (Hydration → Format → Command)

    The replay pipeline receives a MessageContext with ctx.detection already populated
    from the stored OnboardingPendingMessage checkpoint. Hydration still runs in replay so the
    formatter and command factory can load the current sender profile and chat members.
    """
    def __init__(
        self,
        fresh_pipeline: Pipeline,
        replay_pipeline: Pipeline,
        tg_executor: CommandExecutorPort | None,
        dc_executor: CommandExecutorPort | None,
    ):
        self.fresh_pipeline = fresh_pipeline
        self.replay_pipeline = replay_pipeline
        self.routes = {}
        if tg_executor:
            self.routes[Platform.TELEGRAM] = tg_executor
        if dc_executor:
            self.routes[Platform.DISCORD] = dc_executor

    async def process_input(self, data: InputData) -> None:
        """Process a fresh inbound message through the full pipeline."""
        ctx = MessageContext(input=data)
        ctx = await self.fresh_pipeline.run(ctx)
        await self._dispatch(ctx, data.platform)

    async def process_pending(self, pending: OnboardingPendingMessage) -> None:
        """Replay a pending message after onboarding completion.

        The detection checkpoint stored in OnboardingPendingMessage (including geo-resolved tz_resolved)
        is injected into the context here, so replay skips Guard, Aging, Detection,
        GeoResolve, and Registration, then resumes from HydrationStage.
        """
        ctx = MessageContext(
            input=pending.original_input,
            detection=pending.detection,   # checkpoint: detection + geo already done
        )
        ctx = await self.replay_pipeline.run(ctx)
        await self._dispatch(ctx, pending.original_input.platform)

    async def _dispatch(self, ctx: MessageContext, platform: Platform) -> None:
        if not ctx.commands:
            return
        executor = self.routes.get(platform)
        if executor:
            await executor.execute(ctx.commands)
        else:
            logger.warning(f"No executor configured for platform {platform}")
