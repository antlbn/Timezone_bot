from typing import Protocol
from core.domain.value_objects import MessageContext

class Stage(Protocol):
    async def process(self, ctx: MessageContext) -> MessageContext:
        ...
