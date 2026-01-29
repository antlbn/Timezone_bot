# 🤖 Technical Spec: Bot Logic Module

## 1. Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐
│  Telegram API   │────▶│  Connector Module │
└─────────────────┘     └────────┬─────────┘
                                 │
                                 ▼
                        ┌────────────────┐
                        │   Bot Core     │
                        └───┬────────┬───┘
                            │        │
               ┌────────────┘        └────────────┐
               ▼                                  ▼
      ┌─────────────────┐                ┌───────────────┐
      │  SQLite Storage │                │ Transformation │
      │   (user TZs)    │                │    Module      │
      └─────────────────┘                └───────────────┘
```

---

## 2. Core Workflow

### Trigger
Бот слушает все сообщения в чатах и проверяет на срабатывание capture module (обнаружение времени).

### Flow: Happy Path (юзер в БД)

```
1. [TRIGGER]     → Capture module находит время в сообщении
2. [LOOKUP]      → Проверка sender_id в SQLite
3. [FOUND]       → Получаем timezone отправителя
4. [SCAN]        → Получаем список других юзеров чата из БД
5. [TRANSFORM]   → Вызов TTM для конвертации во все зоны
6. [REPLY]       → Бот реплеит сообщение:
                   "🕐 @sender (Europe/Berlin): 14:00
                    ├─ @user1 (America/New_York): 08:00
                    └─ @user2 (Asia/Tokyo): 22:00"
```

### Flow: New User (юзера нет в БД)

```
1. [TRIGGER]     → Capture module находит время
2. [LOOKUP]      → Проверка sender_id в SQLite
3. [NOT FOUND]   → Юзер отсутствует в БД
4. [ASK CITY]    → Бот спрашивает: "В каком городе ты находишься?"
5. [PARSE]       → Попытка определить timezone по городу
   │
   ├─ [SUCCESS]  → Сохраняем в SQLite, выполняем конвертацию, REPLY
   │
   └─ [FAIL]     → Fallback: спрашиваем системное время юзера
                   → Вычисляем timezone по offset
                   → Сохраняем, REPLY
```

---

## 3. Bot Commands (Future)

| Command | Description |
|---------|-------------|
| `/settz <city>` | Установить timezone вручную |
| `/mytz` | Показать текущую timezone |
| `/convert <time> <from> <to>` | Ручная конвертация |

---

## 4. Open Questions

- [ ] Как получать список юзеров чата? (Telegram API ограничения)
- [ ] Кэшировать ли юзеров чата?
- [ ] Rate limiting для ответов бота?
- [ ] Как обрабатывать приватные чаты vs групповые?

