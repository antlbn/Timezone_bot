# 05. Data Storage

- **Persistent:** `SQLiteUserRepository` and `SQLiteChatRepository`. Stores user settings and chat associations.
- **Ephemeral:** `MemoryOnboardingPendingRepository` and `MemoryOnboardingChilloutStateRepository`. Stores onboarding state. Data is lost on restart (MVP trade-off).
