# Project Roadmap & Backlog

This document tracks long-term ideas, deferred features, and known technical debt. For session-by-session history, see [PROGRESS.md](file:///Users/johnwunderbellen/Timezone_bot/journal/PROGRESS.md).

## 🚀 Active LLM Integration Cycle (Current)
- [ ] Connect and verify with local model (Ollama)
- [ ] Finalize LLM evaluation and monitoring setup (Promptfoo)
- [ ] Elaborate and implement comprehensive edge-case tests
- [ ] Conduct live experiments via Telegram and Discord
- [ ] Test with a remote model (OpenAI/Grok)
- [ ] Document final integration results
- [ ] Audit codebase against specifications (resolve contradictions)
- [ ] Update [README.md](file:///Users/johnwunderbellen/Timezone_bot/README.md) and [HANDOVER.md](file:///Users/johnwunderbellen/Timezone_bot/journal/HANDOVER.md) to reflect the new LLM-centric architecture

## 📋 General TO-DO & Technical Debt
- [ ] **CachedDB Validation**: Verify if the in-memory caching layer is fully functional and update `05_storage.md` accordingly.
- [ ] **Disambiguation**: Add a flow for when city search returns multiple results (Future Scope from `06_city_to_timezone.md`).
- [ ] **JIT User Purge**: Implement Just-In-Time member validation before conversion to handle silent leaves (Telegram).
- [ ] **Privacy**: Make time setting messages visible only to the target user (ephemeral/self-destructing).


