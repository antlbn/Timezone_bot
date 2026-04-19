"""
OnboardingCoordinator — Application Service.

Owns onboarding workflow and latest-pending replay:
  1. Persist latest pending message when a sender has no timezone
  2. Suppress repeated prompts during chillout
  3. Resolve city → timezone on completion
  4. Replay the latest pending message if it is still fresh
  5. Clear pending state on completion/decline

Nothing here knows about Telegram, aiogram, Discord, or any UI framework.
author_name is NOT a parameter here — it is synced to the DB by MessageProcessingService
on every message that passes DetectionStage, before onboarding is ever triggered.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.domain.commands import SendReply
from core.domain.enums import Platform
from core.domain.value_objects import MessageContext, OnboardingPendingMessage, BotSettings
from core.pipeline.pipeline import Pipeline
from ports.delivery import DeliveryPort
from ports.geocoding import GeoPort
from ports.onboarding_chillout_state import OnboardingChilloutStatePort
from ports.pending import OnboardingPendingPort
from ports.storage import StoragePort


# ---------------------------------------------------------------------------
# Result value objects (pure data, no behaviour)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OnboardingResult:
    ok: bool
    timezone_name: str | None = None
    city: str | None = None
    flag: str | None = None
    error: str | None = None  # "city_not_found"


# ---------------------------------------------------------------------------
# Application Service
# ---------------------------------------------------------------------------

class OnboardingCoordinator:
    def __init__(
        self,
        storage_port: StoragePort,
        onboarding_pending_port: OnboardingPendingPort,
        chillout_state_port: OnboardingChilloutStatePort,
        geocoding_port: GeoPort,
        replay_pipeline: Pipeline,
        delivery_service: DeliveryPort,
        settings: BotSettings,
    ) -> None:
        self._storage = storage_port
        self._onboarding_pending = onboarding_pending_port
        self._chillout_state = chillout_state_port
        self._geo = geocoding_port
        self._replay_pipeline = replay_pipeline
        self._delivery = delivery_service
        self._settings = settings

    async def store_pending_and_should_prompt(
        self,
        user_id: int,
        platform: Platform,
        pending_message: OnboardingPendingMessage,
    ) -> bool:
        """Store the latest pending message and decide whether the onboarding prompt should be shown."""
        await self._onboarding_pending.upsert(user_id, platform, pending_message)
        return not await self._chillout_state.is_onboarding_in_chillout(
            user_id,
            platform,
            self._settings.onboarding_cooldown_secs,
        )

    async def mark_prompt_shown(self, user_id: int, platform: Platform) -> None:
        await self._chillout_state.mark_onboarding_shown(user_id, platform)

    async def complete(
        self,
        user_id: int,
        city_raw: str,
        platform: Platform,
    ) -> OnboardingResult:
        """User submitted a city name. No author_name needed — already synced in application flow."""
        location = await self._geo.resolve_city(city_raw)
        if location is None:
            return OnboardingResult(ok=False, error="city_not_found")

        # Persist profile so replay hydration/formatting can use the new timezone immediately.
        await self._storage.set_user(
            user_id,
            platform,
            location.timezone,
            location.city,
            location.flag,
        )

        pending_message = await self._onboarding_pending.get(user_id, platform)
        if pending_message:
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
        await self._storage.set_onboarding_declined(user_id, platform)
        await self._onboarding_pending.delete(user_id, platform)

    def _is_replay_stale(self, pending: OnboardingPendingMessage) -> bool:
        age_seconds = (datetime.now(timezone.utc) - pending.original_input.timestamp_utc).total_seconds()
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
