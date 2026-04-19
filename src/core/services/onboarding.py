"""
OnboardingService — Application Service.

Owns ALL orchestration for the onboarding completion flow:
  1. Resolve city → timezone via geocoding
  2. Persist user profile (storage)
  3. Fetch and delete pending messages
  4. Replay each pending message through the replay pipeline via MessageDispatcher

Nothing here knows about Telegram, aiogram, Discord, or any UI framework.
author_name is NOT a parameter here — it is synced to the DB by RegistrationStage
on every message that passes DetectionStage, before onboarding is ever triggered.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.core.domain.enums import Platform
from src.ports.geocoding import GeoPort
from src.ports.pending import PendingPort
from src.ports.storage import StoragePort

if TYPE_CHECKING:
    from src.core.services.dispatcher import MessageDispatcher


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

class OnboardingService:
    def __init__(
        self,
        storage_port: 'StoragePort',
        pending_port: 'PendingPort',
        geocoding_port: 'GeoPort',
        dispatcher: 'MessageDispatcher',
    ) -> None:
        self._storage = storage_port
        self._pending = pending_port
        self._geo = geocoding_port
        self._dispatcher = dispatcher

    async def complete(
        self,
        user_id: int,
        city_raw: str,
        platform: Platform,
    ) -> OnboardingResult:
        """User submitted a city name. No author_name needed — already in DB from RegistrationStage."""
        location = await self._geo.resolve_city(city_raw)
        if location is None:
            return OnboardingResult(ok=False, error="city_not_found")

        # Persist profile — from this point ResolveStage will find the user with a timezone.
        await self._storage.set_user(
            user_id,
            platform,
            location.timezone,
            location.city,
            location.flag,
        )

        # Fetch and atomically delete all pending messages for this user.
        pending_messages = await self._pending.get_and_delete(user_id, platform)

        # Replay through the replay pipeline (Resolve → Format → Command).
        # ctx.detection is pre-loaded from each PendingMessage checkpoint in MessageDispatcher.
        for pending in pending_messages:
            await self._dispatcher.process_pending(pending)

        return OnboardingResult(
            ok=True,
            timezone_name=location.timezone,
            city=location.city,
            flag=location.flag,
        )

    async def decline(self, user_id: int, platform: Platform) -> None:
        """User pressed /skip. author_name already in DB from RegistrationStage.
        Mark as declined so OnboardingGateStage emits NoOp in future.
        Delete pending messages without replay.
        """
        await self._storage.set_onboarding_declined(user_id, platform)
        await self._pending.get_and_delete(user_id, platform)
