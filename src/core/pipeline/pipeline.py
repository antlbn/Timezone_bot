from src.core.domain.value_objects import MessageContext
from src.core.pipeline.contracts import Stage

class Pipeline:
    def __init__(self, stages: list[Stage]):
        self.stages = stages

    async def run(self, ctx: MessageContext) -> MessageContext:
        for stage in self.stages:
            ctx = await stage.process(ctx)
            if ctx._stopped:
                return ctx
        return ctx
