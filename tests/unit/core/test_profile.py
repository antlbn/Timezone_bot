import pytest

from core.domain.enums import Platform
from core.domain.value_objects import UserProfile
from core.services.profile import ProfileService
from tests.fakes.ports import FakeStoragePort


@pytest.mark.asyncio
async def test_profile_service_get_user_delegates_to_storage():
    storage = FakeStoragePort()
    user = UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/Berlin", city="Berlin")
    storage.users[(1, Platform.TELEGRAM)] = user
    service = ProfileService(users_repo=storage, chats_repo=storage)

    result = await service.get_user(1, Platform.TELEGRAM)

    assert result == user


@pytest.mark.asyncio
async def test_profile_service_get_sorted_chat_members_orders_by_offset():
    storage = FakeStoragePort()
    storage.members[("chat1", Platform.TELEGRAM)] = [
        UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="America/New_York", city="New York"),
        UserProfile(user_id=2, platform=Platform.TELEGRAM, timezone="Europe/Berlin", city="Berlin"),
        UserProfile(user_id=3, platform=Platform.TELEGRAM, timezone="Asia/Tokyo", city="Tokyo"),
    ]
    service = ProfileService(users_repo=storage, chats_repo=storage)

    members = await service.get_sorted_chat_members("chat1", Platform.TELEGRAM)

    assert [m.city for m in members] == ["New York", "Berlin", "Tokyo"]


@pytest.mark.asyncio
async def test_profile_service_handles_invalid_timezone_by_sorting_it_first():
    storage = FakeStoragePort()
    storage.members[("chat1", Platform.TELEGRAM)] = [
        UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/Berlin", city="Berlin"),
        UserProfile(user_id=2, platform=Platform.TELEGRAM, timezone="Invalid/TZ", city="Unknown"),
    ]
    service = ProfileService(users_repo=storage, chats_repo=storage)

    members = await service.get_sorted_chat_members("chat1", Platform.TELEGRAM)

    assert [m.city for m in members] == ["Unknown", "Berlin"]
