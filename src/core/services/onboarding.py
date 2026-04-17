"""
OnboardingService — Application Service (core/services layer).

Owns ALL orchestration for the onboarding completion flow:
  1. Resolve city → timezone via geocoding
  2. Persist user profile (storage)
  3. Fetch and delete pending messages
  4. Replay each pending message through the main pipeline
  5. Return ready-to-send dispatches — adapter executes them

Nothing here knows about Telegram, aiogram, or any UI framework.
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
class OnboardingDispatch:
    """One outgoing message produced by replaying a pending message."""

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
        author_name: str,
    ) -> OnboardingResult:
        """
        User submitted a city name.
        """
        location = await self._geo.resolve_city(city_raw)
        if location is None:
            return OnboardingResult(ok=False, error="city_not_found")

        # Persist profile — from this point ResolveStage will find the user.
        await self._storage.set_user(
            user_id,
            platform,
            location.timezone,
            location.city,
            location.flag,
        )

        # Fetch and atomically delete all pending messages for this user.
        pending_messages = await self._pending.get_and_delete(user_id, platform)

        # Messages from the pending queue — use original timestamp (honest data).
        # from_pending=True tells Guard and Aging to skip themselves.
        for pending in pending_messages:
            # Rehydrate the pending message context with detection caching
            await self._dispatcher.process_pending(pending)

        return OnboardingResult(
            ok=True,
            timezone_name=location.timezone,
            city=location.city,
            flag=location.flag,
        )

    async def decline(self, user_id: int, platform: Platform) -> None:
        """
        User pressed /skip.
        Mark as declined so CommandFactoryStage emits NoOp in future.
        Delete pending messages without replay.
        """
        await self._storage.set_onboarding_declined(user_id, platform)
        await self._pending.get_and_delete(user_id, platform)
