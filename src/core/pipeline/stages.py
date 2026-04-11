from datetime import datetime, timezone
from src.core.domain.value_objects import MessageContext
from src.ports.detection import DetectionPort, DetectionRequest
from src.ports.storage import StoragePort
from src.core.services.formatting import format_multi_conversion
from src.core.domain.enums import ResponseStyle


class GuardStage:
    async def process(self, ctx: MessageContext) -> MessageContext:
        if ctx.input.is_bot:
            ctx._stopped = True
            return ctx
        if not ctx.input.text or ctx.input.text.strip() == "":
            ctx._stopped = True
            return ctx
        if len(ctx.input.text) > 4000:
            ctx._stopped = True
            return ctx
        return ctx


class AgingStage:
    def __init__(self, max_age_seconds: int = 120):
        self.max_age_seconds = max_age_seconds

    async def process(self, ctx: MessageContext) -> MessageContext:
        now = datetime.now(timezone.utc)
        age = (now - ctx.input.timestamp_utc).total_seconds()
        if age > self.max_age_seconds:
            ctx._stopped = True
        return ctx


class DetectionStage:
    def __init__(self, detection_port: DetectionPort):
        self.detection_port = detection_port

    async def process(self, ctx: MessageContext) -> MessageContext:
        request = DetectionRequest(text=ctx.input.text, timestamp=ctx.input.timestamp_utc)
        result = await self.detection_port.detect(request)
        ctx.detection = result
        if not result.time_mentioned or not result.points:
            ctx._stopped = True
        return ctx


class ResolveStage:
    def __init__(self, storage_port: StoragePort):
        self.storage_port = storage_port

    async def process(self, ctx: MessageContext) -> MessageContext:
        # Resolve members needed for conversion formatting
        # Here we only need members from storage, GeoPort not strictly needed yet for members
        # as they have timezones already, but let's just make it a pass through for now or fetch members
        return ctx


class FormatStage:
    def __init__(self, storage_port: StoragePort):
        self.storage_port = storage_port

    async def process(self, ctx: MessageContext) -> MessageContext:
        if not ctx.detection or not ctx.detection.points:
            return ctx
        if not ctx.input.sender or not ctx.input.sender.timezone:
            return ctx

        members = await self.storage_port.get_chat_members(ctx.input.chat_id, ctx.input.platform)
        
        ctx.reply_text = format_multi_conversion(
            points=ctx.detection.points,
            sender=ctx.input.sender,
            members=members,
            response_style=ResponseStyle.BLOCK, # config could inject this
            show_usernames=False,
            show_event_title=False
        )
        return ctx
