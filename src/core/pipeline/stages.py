import dataclasses
import logging
from datetime import datetime, timezone

from core.domain.value_objects import MessageContext, PendingMessage, BotSettings, TimePoint
from core.domain.commands import SendReply, SavePending, ShowOnboarding, NoOp
from ports.detection import DetectionPort, DetectionRequest, DetectionResult
from ports.storage import StoragePort
from ports.geocoding import GeoPort
from core.services.formatting import format_multi_conversion

logger = logging.getLogger(__name__)


class GuardStage:
    """Drops messages that should never enter the pipeline."""
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
    """Drops messages that are too old to be worth processing.
    Only used in the fresh pipeline — replay pipeline skips aging entirely
    because replaying is an intentional decision made by OnboardingService.
    """
    def __init__(self, settings: BotSettings):
        self._settings = settings

    async def process(self, ctx: MessageContext) -> MessageContext:
        age_seconds = (datetime.now(timezone.utc) - ctx.input.timestamp_utc).total_seconds()
        if age_seconds > self._settings.max_age_fresh_secs:
            ctx._stopped = True
        return ctx


class DetectionStage:
    """Calls the LLM to detect time mentions. Stops pipeline if none found."""
    def __init__(self, detection_port: DetectionPort):
        self.detection_port = detection_port

    async def process(self, ctx: MessageContext) -> MessageContext:
        request = DetectionRequest(text=ctx.input.text, timestamp=ctx.input.timestamp_utc)
        result = await self.detection_port.detect(request)
        ctx.detection = result
        if not result.time_mentioned or not result.points:
            ctx._stopped = True
        return ctx


class GeoResolveStage:
    """Enriches TimePoints that have an explicit tz_city with a resolved IANA timezone (tz_resolved).
    This happens once in the fresh pipeline; the result is stored in PendingMessage.detection,
    so the replay pipeline does not need to call the geocoder again.
    """
    def __init__(self, geo_port: GeoPort):
        self._geo = geo_port

    async def process(self, ctx: MessageContext) -> MessageContext:
        if not ctx.detection:
            return ctx

        enriched: list[TimePoint] = []
        changed = False
        for point in ctx.detection.points:
            if point.tz_city and not point.tz_resolved:
                location = await self._geo.resolve_city(point.tz_city)
                if location:
                    point = TimePoint(
                        time=point.time,
                        tz_city=point.tz_city,
                        tz_resolved=location.timezone,
                        am_pm_clear=point.am_pm_clear,
                        day_shift=point.day_shift,
                        event_title=point.event_title,
                    )
                    changed = True
                else:
                    logger.debug("GeoResolveStage: could not resolve city %r", point.tz_city)
            enriched.append(point)

        if changed:
            ctx.detection = DetectionResult(
                time_mentioned=ctx.detection.time_mentioned,
                points=tuple(enriched),
            )
        return ctx


class RegistrationStage:
    """Syncs basic user metadata and chat membership. Side-effect only.
    Runs in fresh pipeline after detection to avoid registering one-off noise.
    """
    def __init__(self, storage_port: StoragePort):
        self._storage = storage_port

    async def process(self, ctx: MessageContext) -> MessageContext:
        # Sync persona info
        await self._storage.ensure_user_metadata(
            ctx.input.user_id, ctx.input.platform, ctx.input.author_name
        )

        # Ensure chat membership link exists
        if ctx.input.chat_id:
            await self._storage.add_chat_member(
                chat_id=ctx.input.chat_id,
                user_id=ctx.input.user_id,
                platform=ctx.input.platform,
            )
        return ctx


class HydrationStage:
    """Loads domain context from storage. Strictly read-only.
    Populates ctx.sender and ctx.members (only those with timezones).
    """
    def __init__(self, storage_port: StoragePort):
        self._storage = storage_port

    async def process(self, ctx: MessageContext) -> MessageContext:
        # Load profile if it exists (has timezone, etc.)
        ctx.sender = await self._storage.get_user(ctx.input.user_id, ctx.input.platform)

        # Load only members who can help with time conversion
        if ctx.input.chat_id:
            ctx.members = await self._storage.get_chat_members_with_tz(
                ctx.input.chat_id, ctx.input.platform
            )
        return ctx


class FormatStage:
    """Produces reply_text by converting detected time points.

    Uses tz_resolved (explicit city in message) as source timezone if present.
    Falls back to sender.timezone if no tz_resolved is available.
    Drops silently if neither is available (OnboardingGate or CommandFactory will handle).
    """
    def __init__(self, settings: BotSettings):
        self.settings = settings

    async def process(self, ctx: MessageContext) -> MessageContext:
        if not ctx.detection or not ctx.detection.points:
            return ctx

        has_source = (
            (ctx.sender and ctx.sender.timezone) or
            any(p.tz_resolved for p in ctx.detection.points)
        )
        if not has_source:
            return ctx

        ctx.reply_text = format_multi_conversion(
            points=ctx.detection.points,
            sender=ctx.sender,
            members=ctx.members,
            response_style=self.settings.response_style,
            show_usernames=self.settings.show_usernames,
            show_event_title=self.settings.show_event_title,
        )
        return ctx


class CommandFactoryStage:
    """Produces the final list of Commands based on accumulated context.
    Pure logic — no I/O. All eligibility filtering was done by upstream stages.
    """
    async def process(self, ctx: MessageContext) -> MessageContext:
        if not ctx.detection or not ctx.detection.time_mentioned:
            ctx.commands = [NoOp()]
            return ctx

        # Has a usable source timezone (sender's profile or explicit city in message)?
        # If yes, FormatStage should have produced reply_text.
        has_source = (
            (ctx.sender and ctx.sender.timezone) or
            any(p.tz_resolved for p in ctx.detection.points)
        )
        if has_source:
            if ctx.reply_text:
                ctx.commands = [SendReply(
                    text=ctx.reply_text,
                    chat_id=ctx.input.chat_id,
                    thread_id=ctx.input.thread_id,
                )]
            else:
                logger.warning(
                    "CommandFactoryStage: source timezone present but reply_text is empty — "
                    "FormatStage may have failed silently."
                )
                ctx.commands = [NoOp()]
            return ctx

        # No source timezone. If declined, silently do nothing.
        if ctx.sender and ctx.sender.onboarding_declined:
            ctx.commands = [NoOp()]
            return ctx

        # Save the message for replay after onboarding and prompt the user.
        pending = PendingMessage(original_input=ctx.input, detection=ctx.detection)
        ctx.commands = [
            SavePending(user_id=ctx.input.user_id, platform=ctx.input.platform, message=pending),
            ShowOnboarding(
                user_id=ctx.input.user_id,
                author_name=ctx.input.author_name,
                chat_id=ctx.input.chat_id,
                thread_id=ctx.input.thread_id,
            ),
        ]
        return ctx

