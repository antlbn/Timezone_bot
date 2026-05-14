import tempfile
import pytest
from pathlib import Path

from core.domain.enums import Platform
from adapters.outbound.sqlite_storage import SQLiteStorage


@pytest.fixture
async def sqlite_storage():
    """Фикстура создаёт реальную SQLite базу во временной директории для тестов.
    После теста директория удаляется, что обеспечивает чистую среду."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_bot.db"
        storage = SQLiteStorage(db_path)
        await storage.initialize()
        yield storage
        await storage.close()


@pytest.mark.asyncio
async def test_get_nonexistent_user(sqlite_storage: SQLiteStorage):
    user = await sqlite_storage.get_user(999, Platform.TELEGRAM)
    assert user is None


@pytest.mark.asyncio
async def test_create_and_get_user(sqlite_storage: SQLiteStorage):
    created = await sqlite_storage.create_user(1, Platform.TELEGRAM, "alice")
    assert created.user_id == 1
    assert created.username == "alice"
    assert created.platform == Platform.TELEGRAM
    assert created.timezone is None

    fetched = await sqlite_storage.get_user(1, Platform.TELEGRAM)
    assert fetched is not None
    assert fetched.username == "alice"


@pytest.mark.asyncio
async def test_update_username(sqlite_storage: SQLiteStorage):
    await sqlite_storage.create_user(1, Platform.TELEGRAM, "alice")
    
    # Меняем имя
    await sqlite_storage.update_username(1, Platform.TELEGRAM, "bob")
    
    fetched = await sqlite_storage.get_user(1, Platform.TELEGRAM)
    assert fetched.username == "bob"


@pytest.mark.asyncio
async def test_ensure_user_metadata_creates_or_updates(sqlite_storage: SQLiteStorage):
    # Создаёт если нет
    await sqlite_storage.ensure_user_metadata(2, Platform.TELEGRAM, "charlie")
    fetched1 = await sqlite_storage.get_user(2, Platform.TELEGRAM)
    assert fetched1.username == "charlie"

    # Обновляет если есть
    await sqlite_storage.ensure_user_metadata(2, Platform.TELEGRAM, "charlie_new")
    fetched2 = await sqlite_storage.get_user(2, Platform.TELEGRAM)
    assert fetched2.username == "charlie_new"


@pytest.mark.asyncio
async def test_set_user_updates_timezone_and_location(sqlite_storage: SQLiteStorage):
    # Работает даже если юзера не было (upsert)
    await sqlite_storage.set_user(
        1, Platform.TELEGRAM, timezone="Europe/London", city="London", flag="🇬🇧"
    )
    
    fetched = await sqlite_storage.get_user(1, Platform.TELEGRAM)
    assert fetched.timezone == "Europe/London"
    assert fetched.city == "London"
    assert fetched.flag == "🇬🇧"


@pytest.mark.asyncio
async def test_set_onboarding_declined(sqlite_storage: SQLiteStorage):
    await sqlite_storage.set_onboarding_declined(1, Platform.TELEGRAM)
    
    fetched = await sqlite_storage.get_user(1, Platform.TELEGRAM)
    assert fetched.onboarding_declined is True


@pytest.mark.asyncio
async def test_set_user_clears_onboarding_declined(sqlite_storage: SQLiteStorage):
    await sqlite_storage.set_onboarding_declined(1, Platform.TELEGRAM)

    await sqlite_storage.set_user(
        1, Platform.TELEGRAM, timezone="Europe/London", city="London", flag="🇬🇧"
    )

    fetched = await sqlite_storage.get_user(1, Platform.TELEGRAM)
    assert fetched.timezone == "Europe/London"
    assert fetched.onboarding_declined is False


@pytest.mark.asyncio
async def test_set_onboarding_declined_invalidates_cached_chat_members(sqlite_storage: SQLiteStorage):
    await sqlite_storage.set_user(1, Platform.TELEGRAM, "Europe/London", "London")
    await sqlite_storage.add_chat_member("chat_1", 1, Platform.TELEGRAM)

    members_before = await sqlite_storage.get_chat_members("chat_1", Platform.TELEGRAM)
    assert members_before[0].timezone == "Europe/London"

    await sqlite_storage.set_onboarding_declined(1, Platform.TELEGRAM)

    members_after = await sqlite_storage.get_chat_members("chat_1", Platform.TELEGRAM)
    assert members_after[0].timezone is None
    assert members_after[0].onboarding_declined is True


@pytest.mark.asyncio
async def test_chat_members_flow(sqlite_storage: SQLiteStorage):
    # 1. Подготавливаем двух пользователей (один с таймзоной, другой без)
    await sqlite_storage.set_user(1, Platform.TELEGRAM, "UTC", "Nowhere") # С таймзоной
    await sqlite_storage.ensure_user_metadata(2, Platform.TELEGRAM, "eve") # Строго без таймзоны
    
    # 2. Добавляем в чат
    await sqlite_storage.add_chat_member("chat_1", 1, Platform.TELEGRAM)
    await sqlite_storage.add_chat_member("chat_1", 2, Platform.TELEGRAM)
    
    # 3. Пробуем получить всех (должно быть 2)
    members_all = await sqlite_storage.get_chat_members("chat_1", Platform.TELEGRAM)
    assert len(members_all) == 2
    
    # 4. Проверяем кэш: второе чтение идёт из памяти
    members_cached = await sqlite_storage.get_chat_members("chat_1", Platform.TELEGRAM)
    assert len(members_cached) == 2
    
    # 5. Пробуем получить только с таймзоной (должен быть 1)
    members_tz = await sqlite_storage.get_chat_members_with_tz("chat_1", Platform.TELEGRAM)
    assert len(members_tz) == 1
    assert members_tz[0].user_id == 1
    
    # 6. Удаляем пользователя и проверяем что ушёл
    await sqlite_storage.remove_chat_member("chat_1", 1, Platform.TELEGRAM)
    members_after = await sqlite_storage.get_chat_members("chat_1", Platform.TELEGRAM)
    assert len(members_after) == 1
    assert members_after[0].user_id == 2


@pytest.mark.asyncio
async def test_update_activity(sqlite_storage: SQLiteStorage):
    await sqlite_storage.ensure_user_metadata(1, Platform.TELEGRAM, "alice")
    
    # Проверяем, что запрос выполняется без синтаксических ошибок 
    # (в UserProfile нет last_active_at, так что просто проверяем отсутствие крэша)
    await sqlite_storage.update_activity("chat_1", 1, Platform.TELEGRAM)
