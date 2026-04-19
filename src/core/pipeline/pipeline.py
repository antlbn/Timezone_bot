import logging
from core.domain.value_objects import MessageContext
from core.domain.commands import NoOp
from core.pipeline.contracts import Stage

logger = logging.getLogger(__name__)

class Pipeline:
    def __init__(self, stages: list[Stage]):
        self.stages = stages

    async def run(self, ctx: MessageContext) -> MessageContext:
        for stage in self.stages:
            try:
                ctx = await stage.process(ctx)
                if ctx._stopped:
                    return ctx
            except Exception as e:
                logger.exception(f"Pipeline stage {stage.__class__.__name__} failed: {e}")
                ctx.commands = [NoOp()]
                return ctx
        return ctx
