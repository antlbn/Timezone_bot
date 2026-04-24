# Architecture Decisions & Trade-offs

This document records key technical and product decisions for the current MVP.

## 1. Active Compromises (Accepted Risks)

These are known limitations that were accepted for the MVP to speed up development.

| Decision / Trade-off | Problem | Refactor Trigger | Target Solution |
| :--- | :--- | :--- | :--- |
| **In-memory Onboarding State** | User sessions are lost on restart. | >50 active chats. | Move to **Redis**. Ports are ready. |
| **Best-effort Delivery** | Core logic does not track whether delivery commands were actually executed successfully. | Need retries, delivery status, or compensating actions. | Add command result/ack contract to delivery. |
| **Cross-chat Pending Scope** | Pending onboarding state is currently keyed by `user + platform`, so a newer pending message can overwrite an older one from another chat. | Users actively trigger onboarding from multiple chats. | Keep cooldown global per user, but scope pending messages per chat. |
| **Auto-commits (No UoW)** | Potential partial writes on error. | Scaling to multiple workers. | Implement full Transactions / Unit of Work. |
| **Raw String Formatting** | Hard to do complex UI (bold, buttons). | Need for platform-specific rich UI. | Return `PresentationModel` instead of string. |
| **Anemic Domain Model** | Logic is in services, not entities. | Complex business rules growth. | Move logic into Entities (Rich Model). |

---

## 2. Key Product Decisions

### 2.0 Why This Architecture
The choice of architecture was largely driven by inexperience, and by the feeling that the project needed hard boundaries to get out of a knot of dependencies.

I am sure there were other valid approaches. This one seemed interesting and useful for a first conscious learning project.

The goal was to make the boundaries between core logic, platform adapters, and infrastructure explicit, and to force the code into a shape that was easier to reason about.

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
If AM/PM is unclear, the bot publishes with an `AM/PM?` annotation instead of staying silent.

## 2.7 Current Operational Limitations

The following limitations are part of the current MVP behavior and should be treated as known constraints, not bugs:

- membership is built from observed activity, not from authoritative platform rosters
- onboarding pending state is in memory and is lost on restart
- pending state currently overwrites across chats for the same user and platform
- replay applies only to the latest pending message for a user/platform pair
- replay depends on pending storage retention, not on fresh-message aging rules
- detection uses only the current message and does not inspect prior chat history
- delivery is best-effort and does not report command outcome back to the core

---

## 3. Roadmap (Future Growth)

1. **Interactive AM/PM Clarification**: Ask the user instead of just annotating.
2. **Multi-Message Context**: Feed 3-5 previous messages to the LLM for better context.
3. **Infrastructure Error Handling**: Handle "Bot Blocked" by deactivating users in the DB.
4. **Declarative Pipeline Builder**: Reduce duplication between fresh and replay pipelines.

---

## 4. Archive & History
For historical context on how these decisions were reached, see [docs/archive/](archive/).
