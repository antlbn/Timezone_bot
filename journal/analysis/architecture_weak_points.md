# Architecture Weak Points

This artifact lists the most important architectural weak points found during spec review. These are not hypothetical style notes; they are places where the current design can degrade under load or drift away from its own contracts.

## 1. Synchronous Geocoding in Async Runtime

### What exists now

`src/geo.py` uses synchronous `geopy.Nominatim` calls directly in runtime paths used by:

- Telegram onboarding city setup,
- Discord onboarding city setup,
- event processing when a point contains `city`.

### Why this is weak

The bot is otherwise async. A blocking geocoding call can stall the event loop and delay unrelated chat processing.

### Risk level

High under load.

### Suggested direction

1. move blocking geocoding into a threadpool or async-friendly boundary,
2. add cache for repeated city lookups,
3. isolate provider latency from main chat processing.

## 2. Snapshot Before Lock

### What exists now

Short-term history append/snapshot happens before the per-chat processing lock is acquired.

### Why this is weak

The system guarantees serialized execution, but not perfectly atomic history mutation plus execution order during bursts.

### Risk level

Medium. Mostly visible under heavy chat bursts.

### Suggested direction

Move append/snapshot inside the chat lock if ordering quality becomes more important than throughput.

## 3. External Provider Work Inside Hot Path

### What exists now

City override resolution for event points can trigger geocoding inside the publish/update path.

### Why this is weak

Even registered-user event publishing can become dependent on slow external geo calls if the message contains an explicit city override.

### Risk level

Medium to high depending on traffic and provider reliability.

### Suggested direction

Add geo result caching and consider degrading gracefully when override resolution is unavailable.

## 4. Config Drift

### What exists now

`configuration.yaml` still contains onboarding timeout settings from the removed replay/frozen-message model.

### Why this is weak

Specs and code are converging, but config drift can mislead future maintainers into believing a removed behavior still exists.

### Risk level

Medium for maintainability.

### Suggested direction

Remove dead config keys or mark them deprecated in code and docs until deletion.

## 5. Telegram Membership Accuracy

### What exists now

Telegram membership cleanup is weaker than Discord. It depends more on observed events and manual correction.

### Why this is weak

Missed leave events can leave stale members in conversion output.

### Risk level

Medium.

### Suggested direction

Decide explicitly whether Telegram should stay manual-first or gain a just-in-time verification strategy for suspicious stale records.

## 6. Documentation Sensitivity

### What exists now

A lot of architectural knowledge previously lived in transitional specs instead of stable contracts.

### Why this is weak

When docs drift, rebuildability drops fast, especially around onboarding and memory boundaries.

### Risk level

Medium, but improving.

### Suggested direction

Keep runtime invariants concentrated in a few canonical specs and keep analysis notes separate from source-of-truth documents.
