# Technical Spec: Telegram Commands & UI

## 1. Overview

Bot commands for managing settings and chat members.
Each bot response displays `/tb_help` text at the bottom.

---

## 2. Commands

| Command | Description |
|---------|-------------|
| `/tb_help` | Show command menu |
| `/tb_me` | Show your current location |
| `/tb_settz` | Change your timezone |
| `/tb_members` | List chat members from DB |
| `/tb_remove` | Remove stale member (left chat while bot offline) |

---

## 3. Response Footer

Each bot response ends with the line:

```
14:00 Berlin 🇩🇪 | 08:00 New York 🇺🇸 | 22:00 Tokyo 🇯🇵
/tb_help
```

---

## 4. Command Flows

Commands are divided into three logical modules:

- **settings.py** — personal settings management (`/tb_settz`, `/tb_me`) and FSM `SetTimezone`.
- **members.py** — chat member list management (`/tb_members`, `/tb_remove`) and FSM `RemoveMember`.
- **common.py** — common functions (`/tb_help`), time mention handling and system events (`on_bot_kicked`).



### /tb_help

```
User: /tb_help

Bot:
🕐 Timezone Bot Commands

/tb_me     - your location
/tb_settz  - change TZ  
/tb_members - members
/tb_remove - remove
```

### /tb_me

```
User: /tb_me

Bot: Berlin 🇩🇪 (Europe/Berlin)
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


For code clarity and separation of concerns, helper modules are introduced:
- **src/middleware.py**: Contains logic affecting all incoming messages (member collection).
- **src/states.py**: Contains state classes (FSM) for setup and removal scenarios.

- Commands are split into three files in the src/commands directory

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

