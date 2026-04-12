from datetime import datetime, timezone
from src.core.domain.value_objects import MessageContext, PendingMessage, BotSettings
from src.core.domain.commands import SendReply, SavePending, ShowOnboarding, NoOp
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
        if ctx.input.chat_id:
            # First, ensure sender is in the chat member list (registration)
            if ctx.input.sender:
                await self.storage_port.add_chat_member(
                    chat_id=ctx.input.chat_id,
                    user_id=ctx.input.user_id,
                    platform=ctx.input.platform
                )
            
            # Second, hydrate members list for the entire chat
            ctx.members = await self.storage_port.get_chat_members(
                chat_id=ctx.input.chat_id,
                platform=ctx.input.platform
            )
        return ctx


class FormatStage:
    def __init__(self, settings: BotSettings):
        self.settings = settings

    async def process(self, ctx: MessageContext) -> MessageContext:
        if not ctx.detection or not ctx.detection.points:
            return ctx
        if not ctx.input.sender or not ctx.input.sender.timezone:
            return ctx

        # All IO was handled in ResolveStage, now this is pure logic.
        ctx.reply_text = format_multi_conversion(
            points=ctx.detection.points,
            sender=ctx.input.sender,
            members=ctx.members,
            response_style=self.settings.response_style,
            show_usernames=self.settings.show_usernames,
            show_event_title=self.settings.show_event_title
        )
        return ctx


class CommandFactoryStage:
    async def process(self, ctx: MessageContext) -> MessageContext:
        if not ctx.detection or not ctx.detection.time_mentioned:
            ctx.commands = [NoOp()]
            return ctx

        if ctx.input.sender is not None and ctx.input.sender.timezone:
            if ctx.reply_text:
                ctx.commands = [SendReply(text=ctx.reply_text)]
            else:
                ctx.commands = [NoOp()]
            return ctx

        if ctx.input.sender is None or not ctx.input.sender.onboarding_declined:
            pending = PendingMessage(
                text=ctx.input.text,
                author_name=ctx.input.author_name,
                chat_id=ctx.input.chat_id,
                timestamp_utc=ctx.input.timestamp_utc,
            )
            ctx.commands = [
                SavePending(user_id=ctx.input.user_id, platform=ctx.input.platform, message=pending),
                ShowOnboarding(user_id=ctx.input.user_id, author_name=ctx.input.author_name, chat_id=ctx.input.chat_id)
            ]
            return ctx

        ctx.commands = [NoOp()]
        return ctx
