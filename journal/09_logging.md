# Technical Spec: Logging

## 1. Overview (MVP)
Минималистичная стратегия:
- **Output**: Стандартный вывод (`stdout`) — идеально для Docker.
- **Library**: Встроенный Python `logging`.
- **Никаких сторонних сервисов** (Sentry и т.д. — out of scope).

---

## 2. Configuration

`configuration.yaml`:
```yaml
logging:
  level: INFO   # DEBUG — для разработки, INFO — для продакшена
```

---

## 3. Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Сырые апдейты Telegram (JSON) |
| `INFO` | Основные события: "Bot started", "Converted time for user X" |
| `WARNING` | Нештатные ситуации (API timeout, DB lock), работа продолжается |
| `ERROR` | Критические ошибки (Traceback) |

---

## 4. Simple Context
В сообщение лога просто добавляем ID чата, если он есть:
`[chat:123] Timezone set to Europe/Berlin`

---

## 5. Exception Handling
Мы **не скрываем** ошибки.
- **Failures**: Все исключения в `except` блоках (Geo API, DB) должны логироваться как `WARNING` или `ERROR`.
- **Silent Failures**: `except: pass` **запрещен** для критической логики.
