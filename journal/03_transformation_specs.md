# 03. Transformation Contracts (Pipeline)

Data flows between stages via strict immutable dataclasses (`MessageContext`), not `dict`.
- **LLM Detection:** Returns a strict `DetectionResult` (parsed via Pydantic).
- **Resolution:** `GeoResolveStage` resolves timezones (priority: explicit city -> sender timezone).
- **Transform:** `FormatStage` converts time via UTC pivot for each `UserProfile` in the chat.
