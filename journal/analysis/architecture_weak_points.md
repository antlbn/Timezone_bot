# Architecture Weak Points

This artifact lists the most important architectural weak points found during spec review. These are not hypothetical style notes; they are places where the current design can degrade under load or drift away from its own contracts.

## 1. Snapshot Before Lock

### What exists now

Short-term history append/snapshot happens before the per-chat processing lock is acquired.

### Why this is weak

The system guarantees serialized execution, but not perfectly atomic history mutation plus execution order during bursts.

### Risk level

Medium. Mostly visible under heavy chat bursts.

### Suggested direction

Move append/snapshot inside the chat lock if ordering quality becomes more important than throughput.

## 2. External Provider Work Inside Hot Path

### What exists now

City override resolution for event points can still trigger external geocoding inside the publish/update path on cache misses.

### Why this is weak

The event loop is no longer blocked, but reply latency for that specific message still depends on provider availability.

### Risk level

Medium to high depending on traffic and provider reliability.

### Suggested direction

Keep geo caching, and consider stronger degradation rules when override resolution is unavailable or too slow.

## 3. Documentation Sensitivity

### What exists now

A lot of architectural knowledge previously lived in transitional specs instead of stable contracts.

### Why this is weak

When docs drift, rebuildability drops fast, especially around onboarding and memory boundaries.

### Risk level

Medium, but improving.

### Suggested direction

Keep runtime invariants concentrated in a few canonical specs and keep analysis notes separate from source-of-truth documents.

## Resolved Recently

- Blocking geocoding was moved off the main event loop and wrapped with cache-aware async helpers.
- Dead onboarding replay config was removed from `configuration.yaml`.
- Telegram reply building now prunes stale members just in time before final conversion output.
