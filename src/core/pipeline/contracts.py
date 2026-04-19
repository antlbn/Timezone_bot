from typing import Protocol
from core.domain.value_objects import MessageContext


class Stage(Protocol):
    """A pipeline stage that mutates ctx in-place.

    This implements a 'Mutable Shell / Immutable Core' pattern:
    The MessageContext acts as a mutable shell that lives for a single pipeline run.
    Stages write their results directly into this shell. However, the data inside
    the shell (InputData, DetectionResult, UserProfile, etc.) are all strictly
    immutable (frozen dataclasses or tuples).

    This deliberate design choice avoids the overhead of constantly copying the context
    while guaranteeing that individual data payloads cannot be tampered with.
    It is valid as long as pipeline stages are executed sequentially (no async fan-out).
    """
    async def process(self, ctx: MessageContext) -> None:
        ...
