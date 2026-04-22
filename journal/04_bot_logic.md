# 04. Pipeline Logic (Bot Logic)

Message processing flows through a functional pipeline (`src/core/pipeline/stages.py`):
1. `GuardStage`: Filters out bots and system messages.
2. `AgingStage`: Checks message TTL (prevents processing stale updates via `TimePort`).
3. `DetectionStage`: LLM-based time parsing.
4. `GeoResolveStage`: Resolves coordinates and flags.
5. `HydrationStage`: Loads member profiles from DB.
6. `FormatStage`: Assembles the final text.
7. `DecisionStage`: Generates a domain Command (`SendReply` or `ShowOnboarding`).
