# Technical Spec: Telegram Commands & UI

## 1. Overview

Команды бота для управления настройками и участниками чата.
В каждом ответе бота внизу отображается текст `/tb_help`.

---

## 2. Commands

| Command | Description |
|---------|-------------|
| `/tb_help` | Show command menu |
| `/tb_mytz` | Show your current location |
| `/tb_settz` | Change your timezone |
| `/tb_members` | List chat members from DB |
| `/tb_remove` | Remove member from list |

---

## 3. Response Footer

Каждый ответ бота заканчивается строкой:

```
14:00 Berlin 🇩🇪 | 08:00 New York 🇺🇸 | 22:00 Tokyo 🇯🇵
/tb_help
```

---

## 4. Command Flows

Команды разделены на три логических модуля:

- **settings.py** — управление личными настройками (`/tb_settz`, `/tb_mytz`) и FSM `SetTimezone`.
- **members.py** — управление списком участников чата (`/tb_members`, `/tb_remove`) и FSM `RemoveMember`.
- **common.py** — общие функции (`/tb_help`), обработка упоминаний времени и системные события (`on_bot_kicked`).



### /tb_help

```
User: /tb_help

Bot:
🕐 Timezone Bot Commands

/tb_mytz   - your location
/tb_settz  - change TZ  
/tb_members - members
/tb_remove - remove
```

### /tb_mytz

```
User: /tb_mytz

Bot: "Your timezone: Berlin 🇩🇪 (Europe/Berlin)"
```

### /tb_settz

```
User: /tb_settz

Bot: "What city are you in?"

→ Standard flow from 06_city_to_timezone.md
```

### /tb_members

```
User: /tb_members

Bot:
Chat members:

1. @john - Berlin 🇩🇪
2. @alice - New York 🇺🇸
3. @bob - New York 🇺🇸
4. @yuki - Tokyo 🇯🇵

/tb_remove
```

### /tb_remove

```
User: /tb_remove

Bot: "Enter member number to remove:"

User: 3

Bot: "Removed @bob from chat list"
```

---

## 5. Technical Organization


Для чистоты кода и разделения ответственности вводятся вспомогательные модули:
- **src/middleware.py**: Содержит логику, влияющую на все входящие сообщения (сбор участников).
- **src/states.py**: Содержит классы состояний (FSM) для сценариев настройки и удаления.

- команды разбиты на три файла в каталоге src/commands

## 6. Permissions

| Action | Who can do |
|--------|------------|
| Change own TZ | Any user (self only) |
| View list | Any user |
| Remove member | Any user (anyone) |

**Note:** Removal by anyone — for cases when bot missed user exit. Affects bot DB only, not actual chat membership.

---

## 7. Edge Cases

| Case | Bot Response |
|------|--------------|
| Empty member list | "No registered members in this chat yet" |
| Invalid number | "No member with that number" |
| Remove self | Allowed, with confirmation |

