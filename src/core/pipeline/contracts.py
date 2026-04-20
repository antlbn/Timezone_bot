from typing import Protocol
from core.domain.value_objects import MessageContext


class Stage(Protocol):
    """A pipeline stage that returns an updated context.

    This implements a 'Functional Pipeline / Evolvable Shell' pattern:
    The MessageContext acts as a shell that lives for a single pipeline run.
    Stages return a new context (using dataclasses.replace) with their results.
    The data inside the shell (InputData, DetectionResult, UserProfile, etc.)
    are all strictly immutable, and the context itself is also immutable.
    """
    async def process(self, ctx: MessageContext) -> MessageContext:
        ...
