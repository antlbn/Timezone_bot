# План Миграции — Timezone Bot New Architecture

> **Стратегия**: Cutover. Один процесс. Telegram first.  
> **Спецификация**: [ARCHITECTURE.md](file:///Users/johnwunderbellen/Timezone_bot/docs/ARCHITECTURE.md)

---

## Правила Миграции

1. **Новый код не импортирует старый**. `core/` никогда не импортирует из `event_detection/`, `formatter.py`, `geo.py`.
2. **Зависимости только внутрь**. Если в `core/` появился `import discord` — остановись.
3. **Один вертикальный срез за раз**. Telegram полностью → потом Discord.
4. **Тесты пишутся параллельно**, не после.
5. **Старый код не трогаем** пока новый не green.

---

## M0: Scaffolding

**Цель**: все папки и пустые файлы. Ни строки бизнес-логики.

```
src/
├── core/
│   ├── domain/
│   │   ├── value_objects.py      # TODO
│   │   ├── commands.py           # TODO
│   │   └── enums.py              # TODO
│   ├── pipeline/
│   │   ├── pipeline.py           # TODO
│   │   ├── stages.py             # TODO
│   │   ├── command_factory.py    # TODO
│   │   └── contracts.py          # TODO
│   └── services/
│       ├── conversion.py         # TODO
│       └── formatting.py         # TODO
├── ports/
│   ├── storage.py                # TODO
│   ├── detection.py              # TODO
│   ├── geocoding.py              # TODO
│   └── pending.py                # TODO
├── adapters/
│   ├── inbound/
│   │   ├── telegram/
│   │   └── discord/
│   ├── outbound/
│   └── executors/
└── tests/
    ├── unit/
    ├── integration/
    └── fakes/
```

**Готово когда**: все файлы импортируются без ошибок.

---

## M1: Core Domain — Всё Ядро, Без I/O

**Цель**: ядро написано и покрыто тестами. Ни одного вызова I/O.

### M1.1 — Value Objects + Commands + Enums

**`core/domain/enums.py`**
- `Platform(StrEnum)`: TELEGRAM, DISCORD
- `ResponseStyle(StrEnum)`: BLOCK, INLINE

**`core/domain/value_objects.py`**
- `TimePoint(frozen dataclass)` — `time: str`, `tz_city`, `am_pm_clear`, `day_shift`, валидация HH:MM
- `UserProfile(frozen dataclass)` — `user_id`, `platform: Platform`, `city`, `timezone`, `flag`, `onboarding_declined`
- `PendingMessage(frozen dataclass)` — полные данные сообщения для заморозки
- `MessageContext(dataclass)` — **не frozen**, обогащается по ходу pipeline

**`core/domain/commands.py`**
- `Command` — базовый frozen dataclass
- `SendReply(Command)` — `text: str`
- `SavePending(Command)` — `user_id`, `platform`, `message: PendingMessage`  (не dict!)
- `ShowOnboarding(Command)` — `user_id`, `author_name`, `chat_id`
- `NoOp(Command)`

**Тесты M1.1**:
- `TimePoint("25:00", ...)` → ValueError
- `TimePoint("15:00", ...)` → OK
- frozen: попытка изменить поле → FrozenInstanceError

### M1.2 — Ports (Protocol-интерфейсы)

**`ports/storage.py`** — `StoragePort(Protocol)`:
- `get_user()`, `set_user()`, `get_chat_members()`
- `add_chat_member()`, `remove_chat_member()`, `update_activity()`

**`ports/detection.py`**:
- `DetectionRequest(dataclass)` — `text: str`, `timestamp: datetime`
- `DetectionResult(dataclass)` — `time_mentioned: bool`, `points: tuple[TimePoint, ...]`
- `DetectionPort(Protocol)` — `detect(request) → DetectionResult`

**`ports/geocoding.py`**:
- `Location(dataclass)` — `city`, `timezone` (IANA), `country_code`, `flag`
- `GeoPort(Protocol)` — `resolve_city(name: str) → Location | None`

**`ports/pending.py`** — `PendingPort(Protocol)`:
- `save(user_id, platform, message: PendingMessage) → None`
- `get_and_delete(user_id, platform) → list[PendingMessage]`

### M1.3 — Domain Services

**`core/services/conversion.py`** (из `src/transform.py`):
- `parse_time(text: str) → time | None`
- `convert_time(time_str, from_tz, to_tz) → str`

**`core/services/formatting.py`** (из `src/formatter.py`):
- `format_multi_conversion(points, members) → str`

**Тесты M1.3**:
- `convert_time("15:00", "Europe/Berlin", "Europe/Helsinki")` → `"16:00"`

### M1.4 — Pipeline Stages

**`core/pipeline/contracts.py`**:
- `Stage = Protocol` с `async def process(ctx: MessageContext) → MessageContext`

**`core/pipeline/stages.py`**:

| Stage | Логика | Ранний выход |
|-------|--------|:---:|
| `GuardStage` | бот? пустой? длина>4000? | ✅ |
| `AgingStage` | старше N секунд? | ✅ |
| `DetectionStage` | `DetectionPort.detect()` → `ctx.detection` | ✅ (нет времени) |
| `GeoResolveStage` | `GeoPort.resolve_city()` для `tz_city` → `tz_resolved` | — |
| `RegistrationStage` | `StoragePort.ensure_user_metadata()` + `add_chat_member()` | — |
| `HydrationStage` | `StoragePort.get_user()` + `get_chat_members_with_tz()` | — |
| `FormatStage` | `formatting.format_multi_conversion()` → `ctx.reply_text` | — |

**`core/pipeline/command_factory.py`** (чистая функция):

| Условие | Commands |
|---------|---------|
| `time_mentioned=False` | `[NoOp()]` |
| настроен + есть reply | `[SendReply(reply_text)]` |
| не настроен + не отказался | `[SavePending(...), ShowOnboarding(...)]` |

**`core/pipeline/pipeline.py`**:
```
Pipeline(stages: list[Stage])
  async run(ctx) → ctx:
    for stage in stages:
      ctx = await stage.process(ctx)
      if ctx._stopped: return ctx
    return ctx
```

**Тесты M1.4**:
- GuardStage: bot → stopped
- AgingStage: старое сообщение → stopped
- DetectionStage + FakeDetectionPort: no time → stopped
- DetectionStage + FakeDetectionPort: time found → ctx.detection заполнен
- CommandFactory (без моков): все 3 ветки
- Pipeline integration: "встреча в 15:00" + настроенный user → `[SendReply(text)]`

**Критерий M1**: `pytest tests/unit/ tests/integration/test_pipeline.py` — зелёный.

---

## M2: Telegram Vertical Slice

**Цель**: Telegram message flow полностью через новый pipeline.

### M2.1 — Outbound Adapters

| Файл | Источник | Порт |
|------|---------|------|
| `adapters/outbound/sqlite_storage.py` | `src/storage/` | `StoragePort` |
| `adapters/outbound/openai_detector.py` | `src/event_detection/detector.py` | `DetectionPort` |
| `adapters/outbound/nominatim_geo.py` | `src/geo.py` | `GeoPort` |
| `adapters/outbound/memory_pending.py` | `src/storage/pending.py` | `PendingPort` |

### M2.2 — Command Executors

**`adapters/executors/base.py`** — `BaseCommandExecutor`:
- `execute(commands, context)` → цикл с dispatch
- `_handle_save_pending(cmd)` → `PendingPort.save()` ← **общий для всех**
- `_handle_noop()` → pass ← **общий**
- `_handle_platform(cmd, context)` → abstract

**`adapters/executors/telegram_executor.py`** — `TelegramCommandExecutor(Base)`:
- `SendReply` → `message.answer(text)`
- `ShowOnboarding` → `message.answer(reply_markup=InlineKeyboardMarkup(...))`

### M2.3 — Telegram Inbound Handler (тонкий)

**`adapters/inbound/telegram/handlers.py`**:
```python
async def on_message(message: Message, container: AppContainer):
    sender = await container.storage.get_user(message.from_user.id, Platform.TELEGRAM)
    ctx = MessageContext(input=InputData(
        text=message.text,
        user_id=message.from_user.id,
        platform=Platform.TELEGRAM,
        author_name=message.from_user.full_name,
        timestamp_utc=message.date,
        sender=sender,
        chat_id=str(message.chat.id),
    ))
    ctx = await container.pipeline.run(ctx)
    await container.tg_executor.execute(ctx.commands, TelegramCtx(message))
```

### M2.4 — Composition Root (Telegram)

**`main.py`** (новый, единый):
```python
async def main():
    config = AppConfig.load("configuration.yaml")
    storage = SQLiteStorage(config.db_path)
    pipeline = Pipeline([GuardStage(), AgingStage(), DetectionStage(...), ...])
    tg_executor = TelegramCommandExecutor(pending=InMemoryPending())
    # ... запуск Telegram
    try:
        await dp.start_polling(bot)
    finally:
        await storage.close()
```

**Критерий M2**: Telegram бот запускается из нового `main.py`, обрабатывает "встреча в 15:00", возвращает конвертацию.

---

## M2.5: Discord Vertical Slice

**Добавляем к существующему M2:**

- `adapters/executors/discord_executor.py` — `DiscordCommandExecutor(Base)`:
  - `SendReply` → `Embed`
  - `ShowOnboarding` → `Embed + SetTimezoneView`
- `adapters/inbound/discord/events.py` — тонкий `on_message`
- `adapters/inbound/discord/slash_commands.py` — `/tb_settz`, `/tb_help` (вне pipeline)
- `main.py` — добавить Discord Bot рядом с Telegram в одном event loop

**Критерий M2.5**: один `main.py`, оба бота запущены в одном процессе.

---

## M3: Cleanup

**Что удаляем:**

| Старый файл | Заменён на |
|-------------|-----------|
| `src/event_detection/__init__.py` | `core/pipeline/stages.py` + `command_factory.py` |
| `src/event_detection/detector.py` | `adapters/outbound/openai_detector.py` |
| `src/formatter.py` | `core/services/formatting.py` |
| `src/transform.py` | `core/services/conversion.py` |
| `src/geo.py` | `adapters/outbound/nominatim_geo.py` |
| `src/storage/pending.py` | `adapters/outbound/memory_pending.py` |
| `src/discord_main.py` | `main.py` (единый) |
| `src/commands/common.py` (логика) | `adapters/inbound/telegram/handlers.py` |
| `src/discord/events.py` (логика) | `adapters/inbound/discord/events.py` |

**Success Criteria M3:**

| Проверка | Команда |
|----------|---------|
| Нет legacy импортов в core | `grep -r "event_detection\|formatter\|transform" src/core/` → пусто |
| Нет dict в доменных объектах | `grep -r "Dict\[str, Any\]" src/core/` → пусто |
| Один entrypoint | только `src/main.py` |
| mypy чистый | `mypy src/core src/ports src/adapters` → 0 errors |
| Тесты зелёные | `pytest tests/` → 100% pass |

---

## Что НЕ делаем в этой миграции

- ❌ ContextStage (история сообщений) — отложено
- ❌ SQLite → PostgreSQL — отложено
- ❌ LogWarning/TrackMetric Command — не нужно сейчас
- ❌ Параллельный запуск old/new — только cutover
- ❌ Трогать старый код до зелёных тестов
