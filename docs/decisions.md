# Architecture Decisions & Trade-offs

This document records the "Why" behind the project — conscious technical choices, accepted risks, and the long-term roadmap.

## 1. Active Compromises (Accepted Risks)

These are known limitations that were accepted for the MVP to speed up development.

| Decision / Trade-off | Problem | Refactor Trigger | Target Solution |
| :--- | :--- | :--- | :--- |
| **In-memory Onboarding State** | User sessions are lost on restart. | >50 active chats. | Move to **Redis**. Ports are ready. |
| **Auto-commits (No UoW)** | Potential partial writes on error. | Scaling to multiple workers. | Implement full Transactions / Unit of Work. |
| **Raw String Formatting** | Hard to do complex UI (bold, buttons). | Need for platform-specific rich UI. | Return `PresentationModel` instead of string. |
| **Anemic Domain Model** | Logic is in services, not entities. | Complex business rules growth. | Move logic into Entities (Rich Model). |

---

## 2. Key Product Decisions

### 2.1 UTC Pivot
All conversions go through UTC (`Local -> UTC -> Target`). This avoids direct zone-to-zone arithmetic and handles DST correctly via IANA data.

### 2.2 LLM-Only Detection
The MVP relies on LLM for detection without a regex fallback. This ensures high flexibility for natural language and returns a strict JSON contract.

### 2.3 One-Shot Context
The LLM sees only the current message. This keeps the contract simple and predictable for the MVP.

### 2.4 Lazy Onboarding
Onboarding starts only when a user mentions time. This reduces chat pollution and provides value immediately.

### 2.5 Passive Membership
The bot only knows members it has seen in the chat. lurkers are not converted by design to avoid massive membership indexing.

### 2.6 AM/PM Ambiguity
If AM/PM is unclear, the bot publishes with an `AM/PM?` annotation instead of staying silent. This ensures the user knows the event was detected even if data is missing.

---

## 3. Roadmap (Future Growth)

1. **Interactive AM/PM Clarification**: Ask the user instead of just annotating.
2. **Multi-Message Context**: Feed 3-5 previous messages to the LLM for better context.
3. **Infrastructure Error Handling**: Handle "Bot Blocked" by deactivating users in the DB.
4. **Declarative Pipeline Builder**: Reduce duplication between fresh and replay pipelines.

---

## 4. Archive & History
For historical context on how these decisions were reached, see [docs/archive/](archive/).
