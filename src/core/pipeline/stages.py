import logging
import dataclasses

from core.domain.value_objects import (
    MessageContext,
    OnboardingPendingMessage,
    BotSettings,
    TimePoint,
    UserProfile,
)
from ports.detection import DetectionPort, DetectionRequest, DetectionResult
from ports.repositories import UserRepositoryPort, ChatRepositoryPort
from ports.geocoding import GeoPort
from core.services.formatting import format_multi_conversion

from ports.time import TimePort

logger = logging.getLogger(__name__)


class GuardStage:
    """Drops messages that should never enter the pipeline."""
    def __init__(self, settings: BotSettings):
        self._settings = settings

    async def process(self, ctx: MessageContext) -> MessageContext:
        if ctx.input.is_bot:
            return dataclasses.replace(ctx, stop_processing=True)
        if not ctx.input.text or ctx.input.text.strip() == "":
            return dataclasses.replace(ctx, stop_processing=True)
        if len(ctx.input.text) > self._settings.max_message_hard_skip_chars:
            return dataclasses.replace(ctx, stop_processing=True)
        return ctx


class AgingStage:
    """Drops messages that are too old to be worth processing.
    Only used in the fresh pipeline — replay pipeline skips aging entirely
    because replaying is an intentional decision made by OnboardingCompletionUseCase.
    """
    def __init__(self, settings: BotSettings, time_port: TimePort):
        self._settings = settings
        self._time = time_port

    async def process(self, ctx: MessageContext) -> MessageContext:
        age_seconds = (self._time.now_utc() - ctx.input.timestamp_utc).total_seconds()
        if age_seconds > self._settings.max_age_fresh_secs:
            return dataclasses.replace(ctx, stop_processing=True)
        return ctx


class DetectionStage:
    """Calls the LLM to detect time mentions. Stops pipeline if none found."""
    def __init__(self, detection_port: DetectionPort):
        self.detection_port = detection_port

    async def process(self, ctx: MessageContext) -> MessageContext:
        request = DetectionRequest(text=ctx.input.text, timestamp=ctx.input.timestamp_utc)
        result = await self.detection_port.detect(request)
        if not result.time_mentioned or not result.points:
            return dataclasses.replace(ctx, detection=result, stop_processing=True)
        return dataclasses.replace(ctx, detection=result)


class GeoResolveStage:
    """Enriches TimePoints that have an explicit tz_city with a resolved IANA timezone (tz_resolved).
    This happens once in the fresh pipeline; the result is stored in OnboardingPendingMessage.detection,
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
                    point = dataclasses.replace(point, tz_resolved=location.timezone)
                    changed = True
                else:
                    logger.debug("GeoResolveStage: could not resolve city %r", point.tz_city)
            enriched.append(point)

        if changed:
            new_detection = DetectionResult(
                time_mentioned=ctx.detection.time_mentioned,
                points=tuple(enriched),
            )
            return dataclasses.replace(ctx, detection=new_detection)
        return ctx


class HydrationStage:
    """Loads domain context from storage. Strictly read-only.
    Populates ctx.sender and ctx.members (only those with timezones).
    """
    def __init__(self, users_repo: UserRepositoryPort, chats_repo: ChatRepositoryPort):
        self._users = users_repo
        self._chats = chats_repo

    async def process(self, ctx: MessageContext) -> MessageContext:
        # Load profile if it exists (has timezone, etc.)
        sender = await self._users.get_user(ctx.input.user_id, ctx.input.platform)

        # Load only members who can help with time conversion
        members: tuple[UserProfile, ...] = tuple()
        if ctx.input.chat_id:
            fetched_members = await self._chats.get_chat_members_with_tz(
                ctx.input.chat_id, ctx.input.platform
            )
            members = tuple(fetched_members)
            
        return dataclasses.replace(ctx, sender=sender, members=members)


class FormatStage:
    """Produces reply_text by converting detected time points.

    Uses tz_resolved (explicit city in message) as source timezone if present.
    Falls back to sender.timezone if no tz_resolved is available.
    Drops silently if neither is available; DecisionStage will decide what to do next.
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

        reply_text = format_multi_conversion(
            points=ctx.detection.points,
            sender=ctx.sender,
            members=ctx.members,
            response_style=self.settings.response_style,
            show_usernames=self.settings.show_usernames,
            show_event_title=self.settings.show_event_title,
            reference_date=ctx.input.timestamp_utc,
        )
        return dataclasses.replace(ctx, reply_text=reply_text)


class DecisionStage:
    """Produces the final pipeline decision based on accumulated context.
    Pure logic — no I/O. Workflow side effects are handled by the application layer.
    """
    async def process(self, ctx: MessageContext) -> MessageContext:
        if not ctx.detection or not ctx.detection.time_mentioned:
            return dataclasses.replace(ctx, ignore=True)

        needs_onboarding = not ctx.sender or ctx.sender.needs_onboarding

        pending_message = None
        if needs_onboarding:
            pending_message = OnboardingPendingMessage(original_input=ctx.input, detection=ctx.detection)

        ignore = not ctx.reply_text and pending_message is None
        if ignore:
            has_profile_tz = bool(ctx.sender and ctx.sender.timezone)
            if has_profile_tz:
                logger.warning(
                    "DecisionStage: sender timezone present but no outcome was produced."
                )
        return dataclasses.replace(
            ctx,
            pending_message=pending_message,
            needs_onboarding=needs_onboarding,
            ignore=ignore,
        )
