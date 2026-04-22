from dataclasses import dataclass

from core.domain.commands import SendReply
from core.domain.enums import Platform
from core.domain.value_objects import MessageContext, OnboardingPendingMessage, BotSettings
from core.pipeline.pipeline import Pipeline
from ports.delivery import DeliveryPort
from ports.geocoding import GeoPort
from ports.pending import OnboardingPendingPort
from ports.repositories import UserRepositoryPort, ChatRepositoryPort
from ports.time import TimePort

@dataclass(frozen=True)
class OnboardingResult:
    ok: bool
    timezone_name: str | None = None
    city: str | None = None
    flag: str | None = None
    error: str | None = None  # "city_not_found"

class OnboardingCompletionUseCase:
    """Executes the final stage of onboarding.
    
    Resolves the provided city to a timezone, updates the user's profile,
    and replays any pending messages if they are still fresh.
    """
    def __init__(
        self,
        users_repo: UserRepositoryPort,
        chats_repo: ChatRepositoryPort,
        onboarding_pending_port: OnboardingPendingPort,
        geocoding_port: GeoPort,
        replay_pipeline: Pipeline,
        delivery_service: DeliveryPort,
        settings: BotSettings,
        time_port: TimePort,
    ) -> None:
        self._users = users_repo
        self._chats = chats_repo
        self._onboarding_pending = onboarding_pending_port
        self._geo = geocoding_port
        self._replay_pipeline = replay_pipeline
        self._delivery = delivery_service
        self._settings = settings
        self._time = time_port

    async def complete(
        self,
        user_id: int,
        city_raw: str,
        platform: Platform,
        author_name: str | None = None,
    ) -> OnboardingResult:
        """User submitted a city name."""
        if author_name:
            await self._users.ensure_user_metadata(user_id, platform, author_name)

        location = await self._geo.resolve_city(city_raw)
        if location is None:
            return OnboardingResult(ok=False, error="city_not_found")

        # Persist profile so replay hydration/formatting can use the new timezone immediately.
        await self._users.set_user(
            user_id,
            platform,
            location.timezone,
            location.city,
            location.flag,
        )

        pending_message = await self._onboarding_pending.get(user_id, platform)
        if pending_message:
            # Sync chat membership if we have chat context
            if pending_message.original_input.chat_id:
                await self._chats.add_chat_member(
                    chat_id=pending_message.original_input.chat_id,
                    user_id=user_id,
                    platform=platform,
                )
            
            if self._is_replay_stale(pending_message):
                await self._onboarding_pending.delete(user_id, platform)
            else:
                await self._replay_latest_pending(pending_message)
                await self._onboarding_pending.delete(user_id, platform)

        return OnboardingResult(
            ok=True,
            timezone_name=location.timezone,
            city=location.city,
            flag=location.flag,
        )

    async def decline(self, user_id: int, platform: Platform) -> None:
        """User pressed /skip. author_name is already synced in application flow.
        Mark as declined so future messages without a source timezone are ignored.
        Delete pending messages without replay.
        """
        await self._users.set_onboarding_declined(user_id, platform)
        await self._onboarding_pending.delete(user_id, platform)

    def _is_replay_stale(self, pending: OnboardingPendingMessage) -> bool:
        age_seconds = (self._time.now_utc() - pending.original_input.timestamp_utc).total_seconds()
        return age_seconds > self._settings.max_age_fresh_secs

    async def _replay_latest_pending(self, pending: OnboardingPendingMessage) -> None:
        ctx = MessageContext(
            input=pending.original_input,
            detection=pending.detection,
        )
        ctx = await self._replay_pipeline.run(ctx)
        decision = ctx.decision
        if not decision or decision.ignore or not decision.reply_text:
            return

        await self._delivery.deliver(
            pending.original_input.platform,
            [
                SendReply(
                    text=decision.reply_text,
                    chat_id=pending.original_input.chat_id,
                    thread_id=pending.original_input.thread_id,
                )
            ],
        )
