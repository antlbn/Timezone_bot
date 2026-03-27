# 🔍 Code Review: Timezone Bot

> Оценка с позиции **технического интервью мидла** (2–4 года опыта, должность Middle/Strong Middle Python Developer)

---

## 📌 TL;DR — Общая оценка

| Область | Оценка | Коментарий |
|---|---|---|
| LLM-пайплайн | ✅ Хорошо | Структура LangGraph грамотная, есть pre/action nodes |
| Память / контекст | ⚠️ Есть вопросы | Двойное ограничение с потенциальными дырами |
| Tools / action_node | ✅ В целом ок | Логика publish/update чёткая, есть fallback |
| Онбординг | ✅ Сильная сторона | JIT-стратегия, deep-link, cooldown — всё продумано |
| Архитектура | ⚠️ Есть шероховатости | Дублирование кода, god-function в [common.py](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py) |
| Тестируемость | ✅ Молодец | Тесты есть, LangSmith датасеты — серьёзный подход |
| Prod-качество | ⚠️ Близко | Несколько edge-cases нерешены |

**Вердикт:** скорее всего взял бы на мидла. Код явно думающего человека, а не «написал и забыл». Проект нетривиальный (async, LangGraph, два мессенджера, SQLite + checkpoint DB). Но замечаний достаточно, чтобы обсудить их на интервью и понять, осознанно ли принимались решения.

---

## 🧠 1. LLM-детекция — как устроена и что думаю

### Как устроена

```
Message → process_message() [__init__.py]
    → aging check (до и после lock)
    → per-chat asyncio.Lock
    → detect_event() [detector.py]
        → build system prompt + HumanMessage
        → AsyncSqliteSaver checkpoint (graph_checkpoints.db)
        → graph.compile() + ainvoke()
            → pre_process_node  (LRU trim > 15 msgs)
            → llm_node          (ChatOpenAI + bind_tools)
            → should_continue   (tool_calls? → action : END)
            → action_node       (publish / update side effects)
```

**Что хорошо:**
- LangGraph StateGraph — правильный выбор для agentic loop с инструментами
- [pre_process_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#114-138) защищает SQLite от безграничного роста истории
- [should_continue](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#375-382) + [action_router](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#383-390) — чистый паттерн conditional routing
- `recursion_limit: 5` — защита от бесконечного цикла ошибок
- Aging check дважды (до lock и после) — отличная деталь, говорит о понимании конкурентности

**Что смущает:**

### 🔴 Замечание 1: LLM-клиент создаётся на каждый вызов

```python
# graph.py, llm_node()
llm = ChatOpenAI(model=model_name, temperature=temp, ...)  # каждый раз новый объект
llm_with_tools = llm.bind_tools(tools_list)
```

`ChatOpenAI` — это не тяжёлый объект, но `bind_tools()` создаёт новый декоратор каждый раз. При высокой нагрузке это бесполезный overhead. Правильнее: создавать once при инициализации графа или кешировать в [client.py](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/client.py) (там уже есть singleton-паттерн, но [llm_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#139-208) его не использует).

> При этом [client.py](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/client.py) содержит [get_llm_client()](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/client.py#12-26) → `AsyncOpenAI`, который нигде не используется в продакшне! Он остался как мёртвый код от старой архитектуры.

### 🔴 Замечание 2: `graph.compile()` вызывается на каждое сообщение

```python
# detector.py, detect_event()
async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
    await checkpointer.setup()
    graph = build_agent_graph()
    app = graph.compile(checkpointer=checkpointer)  # compile на каждый вызов!
```

[build_agent_graph()](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#391-404) + `compile()` при каждом сообщении — это **лишняя работа**. Граф не меняется между вызовами. Правильно: компилировать граф один раз при старте, а чекпоинтер подключать отдельно или через dependency injection.

Проблема с `AsyncSqliteSaver` в `async with` — он закрывает соединение после каждого вызова. Это:
1. Overhead на открытие/закрытие соединения при каждом сообщении
2. Потенциальные проблемы при высокой конкурентности (хотя per-chat lock смягчает это)

### 🟡 Замечание 3: [tools.py](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/tools.py) — мёртвый код

[src/event_detection/tools.py](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/tools.py) содержит [execute_convert_time()](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/tools.py#16-98), которая **нигде не вызывается**. Логика перенесена в [_build_reply()](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/detector.py#28-89) внутри [detector.py](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/detector.py). Файл — артефакт предыдущей архитектуры. Засоряет проект, вводит в заблуждение нового разработчика.

---

## 💾 2. Память и контекст — двухуровневая система

### Как работает

| Слой | Механизм | Что хранит |
|---|---|---|
| LangGraph state | `AsyncSqliteSaver` (`graph_checkpoints.db`) | Полная история сообщений per thread_id = `{platform}_{chat_id}` |
| Пользователи | [SQLiteStorage](file:///Users/johnwunderbellen/Timezone_bot/src/storage/sqlite.py#10-202) (`bot_data.db` или подобное) | Пользователи, часовые пояса, chat_members |
| Кэш | `OrderedDict` LRU in-memory | Пользователи (до 10,000 записей) |
| Cooldown | `dict` in-memory | Тайминги onboarding-приглашений |

### Ограничение контекста — двойной механизм

```python
# pre_process_node: удаляет из SQLite если > 15 сообщений
# llm_node: дополнительно slice по context_messages (config, default=5)
# + trim_messages по токенам (max_tokens, default=2500)
```

**Хорошо:** defense in depth — несколько барьеров.

**Плохо:** три разных механизма с разными лимитами и логикой — источник bugs:

### 🔴 Замечание 4: Pre-process vs llm_node contra

[pre_process_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#114-138) удаляет из DB сообщения старше 15-го. Но [llm_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#139-208) берёт только последние [context_messages](file:///Users/johnwunderbellen/Timezone_bot/src/config.py#97-100) (default=5) из **текущего state**. Если pre_process только что удалил с 16-го по N — это нормально. Но если `context_messages=5`, то сообщения 6–15 **хранятся в DB, но никогда не попадают в LLM**. Это waste места в базе без пользы.

Хуже: [pre_process_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#114-138) удаляет по count, [llm_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#139-208) slice по count, `trim_messages` по токенам. Три разных единицы измерения — сложно рассуждать о реальном поведении системы.

**Как лучше:** единая стратегия. Либо trim только в [llm_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#139-208) по токенам (и [pre_process](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#114-138) только для DB hygiene с большим лимитом), либо убрать дублирование.

### 🟡 Замечание 5: LRU-кэш не потокобезопасен

```python
# user_cache.py
_users_snapshot = OrderedDict()  # глобальный mutable dict
```

`asyncio` — single-threaded, поэтому _в большинстве случаев_ это не баг. Но если когда-либо добавят `threading` или `multiprocessing` (например, несколько worker-процессов за одним SQLite), это сломается без предупреждения. Для asyncio-кода — приемлемо, но стоит прокомментировать это ограничение явно.

### 🟡 Замечание 6: Cooldown-состояние теряется при рестарте

```python
# pending.py
_dm_invite_timestamps: dict[tuple[int, str], float] = {}  # in-process
```

При рестарте бота все cooldown-ы сбрасываются. Пользователи, которые отказались от onboarding-а за 5 минут до рестарта, получат его снова. Для production это не катастрофа, но стоит знать. Решение: хранить в Redis или SQLite.

---

## 🛠 3. Tools — как устроены

### Схема

```python
# graph.py — tool-схемы (только описание для LLM, логика в action_node)
@tool
def publish_event(points: list[EventPoint], comment: str = "") -> str:
    pass  # Тело пустое — это просто схема для bind_tools()

@tool  
def update_previous_event(event_ref: int, points: list[EventPoint], comment: str = "") -> str:
    pass

# Реальная логика — в action_node()
```

**Что хорошо:**
- Tools как Pydantic-схемы ([EventPoint](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#38-42)) — правильно, чёткая валидация
- [action_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#210-371) разделяет side effects: publish vs update
- Fallback при [update_previous_event](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#48-52) когда event_ref не найден — хорошая деталь
- Validation в [action_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#210-371) (regexp на HH:MM) — правильная позиция для это

**Что смущает:**

### 🟡 Замечание 7: Паттерн "empty body tools" не очевиден

```python
@tool
def publish_event(points: list[EventPoint], comment: str = "") -> str:
    pass  # <- тело намеренно пустое
```

Это нестандартный паттерн — функции с `pass` как значимый код. Новый разработчик будет искать, где же реально они вызываются и будет в растерянности. Нужен хотя бы чёткий комментарий: `# Schema-only: real execution in action_node`.

Альтернатива: использовать `StructuredTool.from_function()` с `func=None` или просто Pydantic-классы как input schemas — более идиоматично для LangChain.

### 🟡 Замечание 8: [action_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#210-371) слишком большая

[action_node](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/graph.py#210-371) — 161 строка (210–370 в graph.py). Она делает:
1. Извлечение callback-ов из config
2. Валидацию points
3. Registration gate
4. Логику publish
5. Логику update (с внутренним if edit vs delete+republish)

Это нарушение Single Responsibility. Трудно тестировать отдельные части. Как минимум — вынести helper-функции `_execute_publish()` и `_execute_update()`.

### 🔴 Замечание 9: Callbacks через `RunnableConfig.configurable` — anti-pattern

```python
# detector.py
config = {
    "configurable": {
        "send_fn": send_fn,     # async callable
        "edit_fn": edit_fn,
        "delete_fn": delete_fn,
        "build_reply_fn": build_reply_wrapper,
        ...
    }
}
```

Передача async-callable-ов через `configurable` dict — это **не предназначенный способ** использования LangGraph `RunnableConfig`. `configurable` предназначен для thread_id, checkpoint_ns и им подобных примитивных конфигурационных значений. Функции передаются как значения dict без типизации.

Проблемы:
- Нет типизации (any callable принимается)
- Не работает с LangGraph serialization (checkpoint restore)
- Хрупко — опечатка в ключе молча даёт `None`

**Как лучше:** передавать через dependency injection на уровне closure или использовать dependency injection контейнер. Например, создавать [app](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/detector.py#191-203) с `inject`-ed компонентами при старте чата.

---

## 👋 4. Онбординг — сильная часть проекта

### Флоу

```
User пишет в группу
  → LLM всё равно обрабатывает сообщение (строит контекст)
  → Если event detected AND user не зарегистрирован:
      → Проверка cooldown (600s default)
      → Deep-link кнопка в группе → DM
  → В DM: /start?onboard_{user_id}_{chat_id}
      → Валидация что user_id совпадает
      → FSM: waiting_for_city → geo resolve → save → complete
```

**Что хорошо:**
- **JIT-онбординг** — бот не спамит всем новым пользователям, только тем, кто реально упомянул событие. Это умно.
- **Deep-link с payload** — `onboard_{user_id}_{chat_id}` передаёт контекст, и после регистрации пользователь сразу добавляется в правильный чат.
- **Security check** в deep-link: `if user_id != target_user_id` — хорошо.
- **Cooldown** на повторный invite — не спамит.
- **`onboarding_declined` флаг** — уважаем выбор пользователя.
- **Fallback** при geo-ошибке: просит текущее время → вычисляет timezone из offset. Реально думала об edge cases.
- **FSM (aiogram)** для многошагового ввода — правильный инструмент.
- **Auto-cleanup** приглашения из группового чата (asyncio.create_task) — UX деталь.

**Что смущает:**

### 🟡 Замечание 10: [cmd_settz](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#98-125) симулирует `/start`

```python
# common.py
async def cmd_settz(message: Message, state: FSMContext):
    if is_dm:
        from src.commands.settings import dm_onboarding_start
        return await dm_onboarding_start(message, None, state)  # None вместо CommandObject
```

Передавать `None` как `CommandObject` — хрупко. Если [dm_onboarding_start](file:///Users/johnwunderbellen/Timezone_bot/src/commands/settings.py#30-108) когда-нибудь обратится к `command.args` без проверки на None, будет AttributeError. Лучше: вынести общую логику в отдельный helper `_show_onboarding_or_settings()`.

### 🟡 Замечание 11: [handle_time_mention](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#127-275) — God Function

[handle_time_mention](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#127-275) в [common.py](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py) — это 155-строчная функция, которая:
1. Проверяет регистрацию
2. Обновляет активность
3. Определяет [send_fn](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#151-166), [edit_fn](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#167-186), [delete_fn](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#187-192), [filter_members_fn](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#193-213) (4 вложенных async closure)
4. Вызывает LLM-пайплайн
5. Обрабатывает онбординг
6. Создаёт asyncio.create_task для cleanup

Это всё в одном месте. Тестировать тяжело, читать — тоже. Лучше разбить на: `_build_platform_callbacks()`, `_trigger_onboarding_invite_if_needed()`.

### 🟡 Замечание 12: Middleware делает лишний DB-вызов

```python
# middleware.py
user = await storage.get_user(event.from_user.id, platform="telegram")
if user:
    await storage.add_chat_member(...)
```

Middleware на каждом сообщении делает SELECT в SQLite. [get_chat_members](file:///Users/johnwunderbellen/Timezone_bot/src/storage/sqlite.py#182-196) потом вызывается снова при форматировании ответа. При этом нет кэша для [chat_members](file:///Users/johnwunderbellen/Timezone_bot/src/storage/sqlite.py#182-196) (только для users). При активном чате — это N запросов в DB на каждое сообщение. Лучше: использовать [get_user_cached()](file:///Users/johnwunderbellen/Timezone_bot/src/storage/user_cache.py#12-40) в middleware.

---

## 📐 Архитектурные наблюдения

### Хорошие практики

| Практика | Где |
|---|---|
| Абстрактный интерфейс хранилища ([Storage](file:///Users/johnwunderbellen/Timezone_bot/src/storage/base.py#5-68) ABC) | [storage/base.py](file:///Users/johnwunderbellen/Timezone_bot/src/storage/base.py) |
| Dependency Injection через callable | [send_fn](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#151-166), [edit_fn](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#167-186), [filter_members_fn](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#193-213) |
| Per-chat concurrency lock | [runtime.py](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/runtime.py) |
| WAL режим SQLite | [sqlite.py](file:///Users/johnwunderbellen/Timezone_bot/src/storage/sqlite.py) |
| Двойная проверка staleness (до и после lock) | [__init__.py](file:///Users/johnwunderbellen/Timezone_bot/src/__init__.py) |
| Config через YAML + env | [config.py](file:///Users/johnwunderbellen/Timezone_bot/src/config.py) |
| Единый `data_retention_days` с автоочисткой | [sqlite.py](file:///Users/johnwunderbellen/Timezone_bot/src/storage/sqlite.py) |

### Паттерны с вопросами

| Проблема | Серьёзность |
|---|---|
| [tools.py](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/tools.py) — мёртвый, нигде не используется | 🟡 Средняя |
| [client.py](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/client.py) [get_llm_client()](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/client.py#12-26) — мёртвый код | 🟡 Средняя |
| `SYSTEM_PROMPT_old` в [prompts.py](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/prompts.py) — старый промпт не удалён | 🟢 Низкая |
| `graph.compile()` на каждое сообщение | 🔴 Высокая |
| Callbacks через `configurable` dict | 🔴 Высокая (при масштабировании) |
| God-function [handle_time_mention](file:///Users/johnwunderbellen/Timezone_bot/src/commands/common.py#127-275) | 🟡 Средняя |
| Cooldown state теряется при рестарте | 🟡 Средняя |

---

## 💬 Как бы сделал иначе

### 1. Скомпилировать граф один раз

```python
# event_detection/app.py (новый файл)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

_app = None

async def get_agent_app():
    global _app
    if _app is None:
        checkpointer = AsyncSqliteSaver(...)
        await checkpointer.setup()
        graph = build_agent_graph()
        _app = graph.compile(checkpointer=checkpointer)
    return _app
```

### 2. Заменить callbacks-через-config на Context Object

```python
@dataclass
class ChatContext:
    chat_id: str
    platform: str
    sender_registered: bool
    send_fn: Callable
    edit_fn: Callable
    delete_fn: Callable
    build_reply_fn: Callable

# Передавать как часть state или через dependency injection
```

### 3. Унифицировать стратегию trim

```python
# Один механизм: DB хранит N!=15 сообщений для hygiene
# LLM видит только последние context_messages - токен-лимит через trim_messages
# Убрать дублирующий slice в llm_node
```

### 4. Удалить мёртвый код

- [tools.py](file:///Users/johnwunderbellen/Timezone_bot/src/event_detection/tools.py) → удалить или оставить как `legacy/`
- `client.py::get_llm_client()` → удалить
- `SYSTEM_PROMPT_old` → удалить

### 5. Сохранять cooldown-ы в SQLite

```python
# Добавить таблицу: onboarding_invites(user_id, platform, sent_at)
# Тогда рестарт не обнуляет состояние
```

---

## 🎯 Итог: что бы подумал на интервью

**Хорошее впечатление:**
- Кандидат умеет работать с async Python, LangGraph, aiogram
- Архитектурное мышление есть: Storage ABC, per-chat lock, JIT-онбординг
- Думает о UX: cooldown, deep-link, auto-cleanup, declined-флаг
- Есть тесты и LangSmith датасеты — серьёзно относится к качеству

**Вопросы на интервью:**
1. "Почему `graph.compile()` вызывается на каждое сообщение? Осознанно?"
2. "Почему callbacks через `configurable`? Знаешь ли о ограничениях?"
3. "Три лимита на контекст — pre_process/context_limit/token_trim — как ты рассуждаешь об их взаимодействии?"
4. "Что произойдёт с onboarding cooldown-ами при рестарте?"

Если кандидат объяснит первые два как осознанный trade-off (например, "compile дешёвое, решил не усложнять") — ок. Если не знает о проблеме — желтый флаг. Если осознаёт, но объяснит почему это приемлемо для текущего масштаба — это и есть мышление хорошего мидла.

**Вывод:** код на сильного Junior/слабого Middle. Взял бы, но с испытательным сроком и ментором.
