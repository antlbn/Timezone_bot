import logging
import dataclasses
from core.domain.value_objects import MessageContext
from core.pipeline.contracts import Stage

logger = logging.getLogger(__name__)


class Pipeline:
    """Executes a linear orchestration flow for message processing.

    Each stage reads the current MessageContext, performs its step, and returns
    an updated context for the next stage.
    """
    
    def __init__(self, stages: list[Stage]):
        self.stages = stages

    async def run(self, ctx: MessageContext) -> MessageContext:
        for stage in self.stages:
            try:
                ctx = await stage.process(ctx)
                if ctx.stop_processing:
                    return ctx
            except Exception as e:
                logger.exception(
                    "Pipeline stage %s failed for user=%s chat=%s text_snippet=%r: %s",
                    stage.__class__.__name__,
                    ctx.input.user_id,
                    ctx.input.chat_id,
                    ctx.input.text[:50] if ctx.input.text else "",
                    e,
                )
                return dataclasses.replace(
                    ctx,
                    failed_stage=stage.__class__.__name__,
                    stop_processing=True,
                )
        return ctx
