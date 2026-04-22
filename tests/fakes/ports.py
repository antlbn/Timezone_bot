from __future__ import annotations

import dataclasses
from core.domain.enums import Platform
from core.domain.value_objects import UserProfile, OnboardingPendingMessage, TimePoint
from ports.detection import DetectionRequest, DetectionResult
from ports.geocoding import Location
from core.domain.commands import Command

from ports.repositories import UserRepositoryPort, ChatRepositoryPort
from ports.time import TimePort
from datetime import datetime, timezone


class FakeTimePort(TimePort):
    def __init__(self, now: datetime | None = None):
        self._now = now or datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    def now_utc(self) -> datetime:
        return self._now

    def now_tz(self, tz_name: str) -> datetime:
        from zoneinfo import ZoneInfo
        return self._now.astimezone(ZoneInfo(tz_name))


class FakeStoragePort(UserRepositoryPort, ChatRepositoryPort):
    def __init__(self):
        self.users: dict[tuple[int, Platform], UserProfile] = {}
        self.members: dict[tuple[str, Platform], list[UserProfile]] = {}
        self.created: list[tuple[int, Platform, str]] = []   # (user_id, platform, name) on first contact
        self.name_updates: list[tuple[int, Platform, str]] = []  # (user_id, platform, name) on name change

    async def initialize(self) -> None:
        pass

    async def get_user(self, user_id: int, platform: Platform) -> UserProfile | None:
        return self.users.get((user_id, platform))

    async def create_user(self, user_id: int, platform: Platform, author_name: str) -> UserProfile:
        profile = UserProfile(user_id=user_id, platform=platform, username=author_name)
        self.users[(user_id, platform)] = profile
        self.created.append((user_id, platform, author_name))
        return profile

    async def update_username(self, user_id: int, platform: Platform, author_name: str) -> None:
        existing = self.users.get((user_id, platform))
        if existing:
            self.users[(user_id, platform)] = dataclasses.replace(existing, username=author_name)
        self.name_updates.append((user_id, platform, author_name))

    async def ensure_user_metadata(self, user_id: int, platform: Platform, username: str) -> None:
        existing = self.users.get((user_id, platform))
        if existing:
            self.users[(user_id, platform)] = dataclasses.replace(existing, username=username)
            self.name_updates.append((user_id, platform, username))
        else:
            self.users[(user_id, platform)] = UserProfile(user_id=user_id, platform=platform, username=username)
            self.created.append((user_id, platform, username))

    async def set_user(self, user_id: int, platform: Platform, timezone: str, city: str | None = None, flag: str | None = None) -> None:
        existing = self.users.get((user_id, platform))
        self.users[(user_id, platform)] = UserProfile(
            user_id=user_id,
            platform=platform,
            username=existing.username if existing else None,
            city=city,
            timezone=timezone,
            flag=flag,
        )

    async def set_onboarding_declined(self, user_id: int, platform: Platform) -> None:
        existing = self.users.get((user_id, platform))
        self.users[(user_id, platform)] = UserProfile(
            user_id=user_id,
            platform=platform,
            username=existing.username if existing else None,
            city=existing.city if existing else None,
            timezone=existing.timezone if existing else None,
            flag=existing.flag if existing else None,
            onboarding_declined=True,
        )

    async def get_chat_members(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        return self.members.get((chat_id, platform), [])

    async def get_chat_members_with_tz(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        all_members = self.members.get((chat_id, platform), [])
        return [m for m in all_members if m.timezone is not None]

    async def add_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        members = self.members.setdefault((chat_id, platform), [])
        if any(m.user_id == user_id for m in members):
            return
        
        # In a real DB, joining chat ensures user exists. In fake, we try to find them.
        profile = self.users.get((user_id, platform))
        if profile:
            members.append(profile)

    async def remove_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        pass

    async def update_activity(self, chat_id: str, user_id: int, platform: Platform) -> None:
        pass


class FakeDetectionPort:
    def __init__(self, time_mentioned: bool = True, points: list[TimePoint] | None = None):
        self._time_mentioned = time_mentioned
        self._points = points or []

    async def detect(self, request: DetectionRequest) -> DetectionResult:
        return DetectionResult(
            time_mentioned=self._time_mentioned,
            points=tuple(self._points)
        )


class FakeGeoPort:
    def __init__(self, resolves_to: Location | None = None):
        self._resolves_to = resolves_to

    async def resolve_city(self, name: str) -> Location | None:
        return self._resolves_to


class FakeOnboardingPendingPort:
    def __init__(self):
        self.messages: dict[tuple[int, str], OnboardingPendingMessage] = {}

    async def upsert(self, user_id: int, platform: Platform, message: OnboardingPendingMessage) -> None:
        self.messages[(user_id, platform.value)] = message

    async def get(self, user_id: int, platform: Platform) -> OnboardingPendingMessage | None:
        return self.messages.get((user_id, platform.value))

    async def delete(self, user_id: int, platform: Platform) -> None:
        self.messages.pop((user_id, platform.value), None)

    async def get_and_delete(self, user_id: int, platform: Platform) -> OnboardingPendingMessage | None:
        message = await self.get(user_id, platform)
        await self.delete(user_id, platform)
        return message


class FakeOnboardingChilloutStatePort:
    def __init__(self, in_chillout: bool = False):
        self.in_chillout = in_chillout
        self.marked: list[tuple[int, Platform]] = []
        self.checked: list[tuple[int, Platform, int]] = []

    async def is_onboarding_in_chillout(
        self,
        user_id: int,
        platform: Platform,
        cooldown_seconds: int,
    ) -> bool:
        self.checked.append((user_id, platform, cooldown_seconds))
        return self.in_chillout

    async def mark_onboarding_shown(self, user_id: int, platform: Platform) -> None:
        self.marked.append((user_id, platform))


class FakeDeliveryPort:
    def __init__(self):
        self.delivered: list[tuple[Platform, list[Command]]] = []

    async def deliver(self, platform: Platform, commands: list[Command]) -> None:
        self.delivered.append((platform, commands))


class FakeCommandExecutorPort:
    def __init__(self):
        self.executed_commands: list[Command] = []

    async def execute(self, commands: list[Command]) -> None:
        self.executed_commands.extend(commands)
