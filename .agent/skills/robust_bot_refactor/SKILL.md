---
name: Robust Bot Refactoring
description: High-level principles for building lean, reliable, and maintainable bots.
---

# Robust Bot Refactoring: The Lean Philosophy

This skill provides a high-level framework for evolving a bot from a prototype to a stable, production-ready system by focusing on simplicity and systemic reliability.

## 1. Minimal Persistence
Apply "The Algorithm" to data.
- **Requirement Audit**: Do you really need to store this? If it's transient, keep it in memory.
- **Stable Foundation**: Use SQLite for its simplicity and single-file nature. Avoid external database dependencies (like Redis) unless strictly necessary for scale.
- **Efficiency**: Use WAL mode and persistent connections to minimize overhead.

## 2. Intelligent Memory
Don't let the bot grow unbounded.
- **Bounded Caches**: Every in-memory data structure must have a limit (LRU).
- **Pruning**: Regularly "garbage collect" stale states or configurations. If it hasn't been used, it shouldn't be taking up resources.

## 3. High-Signal Processing
Focus on what matters.
- **Contextual Logging**: Don't log everything; log the right things. Use adapters to automatically attach context (Platform IDs, User IDs) so you can trace issues instantly.
- **Clean Event Flow**: Minimize the layers between a platform event and its handler. Every layer is a potential point of failure.

## 4. Platform Fluidity
Abstract the platform, not the logic.
- **Logic Isolation**: Keep the core bot logic (time conversion, event detection) decoupled from Discord/Telegram specifics.
- **Background Lean**: Use platform-native task runners for cleanup, but keep them focused on "deleting" or "cleaning" rather than "adding" complexity.

## 5. Radical Testing
Test the intent, not just the code.
- **Ephemeral State**: Tests should start with nothing and leave nothing behind.
- **Failure Analysis**: Use tests to find things that can be deleted. If a test is too hard to write, the code is likely too complex.

> [!IMPORTANT]
> Always refer to the [Constitution](file:///Users/johnwunderbellen/Timezone_bot/.agent/CONSTITUTION.md) before starting any refactor. The goal is to make the bot better by making it smaller.
