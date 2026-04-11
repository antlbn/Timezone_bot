from typing import Protocol
from src.core.domain.value_objects import MessageContext

class Stage(Protocol):
    async def process(self, ctx: MessageContext) -> MessageContext:
        ...
