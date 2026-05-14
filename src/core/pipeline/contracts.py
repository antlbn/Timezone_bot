from typing import Protocol
from core.domain.value_objects import MessageContext


class Stage(Protocol):
    """A pipeline stage that returns an updated context.

    A stage may validate input, call external services, load data, or enrich the
    current workflow state. It returns the context that the next stage should see.
    """
    async def process(self, ctx: MessageContext) -> MessageContext:
        ...
