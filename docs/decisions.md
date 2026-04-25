# Architecture Decisions & Trade-offs

This document records key technical and product decisions for the current MVP.

## 1. Active Compromises (Accepted Risks)

These are known limitations that were accepted for the MVP to speed up development.

| Decision / Trade-off | Problem | Refactor Trigger | Target Solution |
| :--- | :--- | :--- | :--- |
| **In-memory Onboarding State** | User sessions are lost on restart. | >50 active chats. | Move to **Redis**. Ports are ready. |
| **Best-effort Delivery** | Core logic does not track whether delivery commands were actually executed successfully. | Need retries, delivery status, or compensating actions. | Add command result/ack contract to delivery. |
| **Best-effort Pending Replay** | Pending messages are replayed after timezone save, but replay is still best-effort and in-memory only. | Need stronger recovery guarantees or multi-process safety. | Persist pending state in durable storage and define replay result handling. |
| **Auto-commits (No UoW)** | Potential partial writes on error. | Scaling to multiple workers. | Implement full Transactions / Unit of Work. |
| **Raw String Formatting** | Hard to do complex UI (bold, buttons). | Need for platform-specific rich UI. | Return `PresentationModel` instead of string. |
| **Anemic Domain Model** | Logic is in services, not entities. | Complex business rules growth. | Move logic into Entities (Rich Model). |
| **Silent Pipeline Failures** | Pipeline swallows stage exceptions and returns `ignore=True`. System failures look like "no time detected" to the user. | Need for high reliability and monitoring. | Implement `PipelineStageError` hierarchy and bubble up infrastructure errors. |

---

## 2. Key Product Decisions

### 2.0 Why This Architecture & Project Goals
The choice of architecture was largely driven by the goal of **learning architectural patterns** (Hexagonal, Pipe & Filters, Command) and **practicing pair programming with AI**. 

**Цель проекта для меня — не довести систему до идеала, а научиться паттернам проектирования и эффективной работе с ИИ.**

Доведение до идеала всех второстепенных аспектов (таких как идеальное логирование или 100% обработка краевых случаев) намеренно вынесено за скобки для экономии времени. Если потребуется для реальной эксплуатации — это будет доделано, но сейчас фокус на структуре и «чистоте» границ.

### 2.1 UTC Pivot
All conversions go through UTC (`Local -> UTC -> Target`). This avoids direct zone-to-zone arithmetic and handles DST correctly via IANA data.

### 2.2 LLM-Only Detection
The MVP relies on LLM for detection without a regex fallback. This ensures high flexibility for natural language and returns a strict JSON contract.

### 2.3 One-Shot Context
The LLM sees only the current message. This keeps the contract simple and predictable for the MVP.

### 2.4 Lazy Onboarding
Onboarding starts only when a user mentions time. This reduces chat pollution and provides value immediately.

### 2.5 Passive Membership
The bot only knows members it has seen in the chat. Members the bot has not observed are not converted.

This is partly a product decision and partly a platform constraint:

- Telegram does not provide a simple, reliable full-member snapshot for normal group-bot flows
- building a full member directory would require heavier coupling to platform-specific behavior
- keeping membership passive keeps the shared core simpler and avoids broad background synchronization

### 2.6 AM/PM Ambiguity
If AM/PM is unclear, the bot publishes with an `AM/PM?` annotation instead of staying silent. - look into roadmap to solve it.

### 2.8 Error Handling & Logging Strategy
На текущем этапе в проекте отсутствует комплексная стратегия логирования. Это осознанный компромисс:
- **Как сейчас:** 
    - Ошибки внутри стадий Pipeline логируются как `exception` (с трейсбэком), а Pipeline помечает контекст через `failed_stage`. Это защищает бота от падения и позволяет отличить технический сбой от обычного `ignore`, но полноценной классификации ошибок пока нет.
    - Глобальные ошибки в адаптерах ловятся Middleware, логируются и выводят пользователю дружелюбное «что-то пошло не так».
- **Почему так:** Разработка полноценной стратегии классификации ошибок (Domain vs Infrastructure) требует времени, которое сейчас приоритетнее направить на изучение архитектурных слоев.
- **Что сделано:** Базовое покрытие логами критических путей (I/O, DI, Pipeline) присутствует.

## 2.9 Current Operational Limitations

The following limitations are part of the current MVP behavior and should be treated as known constraints, not bugs:

- membership is built from observed activity, not from authoritative platform rosters
- onboarding pending state is in memory and is lost on restart
- replay is best-effort; if replay fails after timezone save, pending may be dropped
- pending keeps only the latest relevant message per chat, not a history
- replay depends on pending storage retention, not on fresh-message aging rules
- detection uses only the current message and does not inspect prior chat history
- delivery is best-effort and does not report command outcome back to the core

---

## 3. Roadmap (Future Growth)

1. **Interactive AM/PM Clarification**: Ask the user instead of just annotating.
2. **Multi-Message Context**: Feed 3-5 previous messages to the LLM for better context.
3. **Infrastructure Error Handling**: Handle "Bot Blocked" by deactivating users in the DB.
4. **pipeline logging strategy** - define domain vs infrastructure errors and handle them accordingly.

---

## 4. Archive & History
For historical context on how these decisions were reached, see [docs/archive/](archive/).
