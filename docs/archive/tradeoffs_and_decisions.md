# Architecture Decision Log & Trade-offs (Handover)

This document records conscious technical trade-offs, assumptions, and open architectural questions. This table explains **why** a decision was made, what the risks are, and **when** it should be refactored (Phase Transition).

## 1. Active Compromises (Accepted Risks & Trade-offs)

| Decision / Trade-off | What is the problem? | When to refactor? | What to change it to? |
| :--- | :--- | :--- | :--- |
| **In-memory Onboarding State** | User sessions are lost upon bot restart (frozen input state). | Production release / >10 active chats / >50 new users per week. | Replace with **Redis**. Interfaces for this are already fully prepared. |
| **Auto-commits instead of transactions (No Unit of Work)** | On error, partial data might be written to the DB. | Scaling (multiple bot workers) or moving cache to a separate DB (Redis). | Implement full transactions per scenario. Currently acceptable: partial cache entries simply expire via TTL. |
| **Text is assembled into a raw string** | Hard to implement complex visual formatting (bold text, buttons) specifically for Telegram and Discord. | Need for complex UI elements inside text messages. | Return an abstract `PresentationModel` object from the core instead of a string, letting the adapter decide how to render it. Kept simple for now (YAGNI). |
| **Anemic Domain Model (FP style)** | Dataclasses only store data, logic is spread across services. Not quite OOP. | Significant complication of business rules and validation. | Move methods and logic inside the entities themselves (Rich Model). Current approach is intentional: easier for beginners to reason about. |

*Note: Dynamic chat-based bot configuration via UI is consciously left **Out of Scope** for the current MVP.*

## 2. Key Architectural Decisions and Patterns

| Pattern | How it works (Concept) | Benefit (Why we need it) |
| :--- | :--- | :--- |
| **Hexagonal Architecture (Ports & Adapters)** | The core is isolated from the outside world (Telegram, DB, LLM) via abstract interfaces. | 100% testability without network. Easy to add a new platform (Discord) without changing the core. |
| **Pipes & Filters (Pipeline)** | A message flies through a "pipe" of independent filter stages (Guard -> Detection -> Format). | Prevents spaghetti code. Each step is isolated, easy to read, and easy to add new checks. |
| **Command Pattern (Decision vs Execution)** | The core only "thinks" and returns intent objects (`SendReply`), it never makes HTTP requests itself. | Business logic is protected from network failures. Core decides *what* to do, adapters decide *how*. |
| **Dependency Injection (Composition Root)** | No global variables. All services are wired together like Lego in `main.py` and passed via `__init__`. | Prevents hidden coupling. Explicit dependencies. Easy to pass fakes (mocks) in tests. |

## 3. SOLID Principles in the Project

The architecture strictly follows SOLID principles. Here is how it looks in practice:

| Principle | Meaning | How it is applied here |
| :--- | :--- | :--- |
| **S** - Single Responsibility | A class should have only one reason to change. | Each pipeline stage does exactly one thing. The onboarding "God Object" was split into two narrow services. |
| **O** - Open/Closed | Open for extension, closed for modification. | To add Discord, we didn`t rewrite the core. We just wrote a new Adapter (extended), without touching old code. |
| **L** - Liskov Substitution | Objects should be replaceable by their subtypes without breaking the program. | A fake `FakeTimePort` plugs in instead of the real `RealTimeAdapter`, and the core works exactly the same. |
| **I** - Interface Segregation | Many narrow interfaces are better than one fat interface. | Interfaces (Ports) are tiny. `TimePort` has only one method: `now()`. |
| **D** - Dependency Inversion | Depend on abstractions, not concrete implementations. | Domain does not import `aiogram` or `aiosqlite`. It imports abstractions from `src/ports/`. Details depend on abstractions. |
