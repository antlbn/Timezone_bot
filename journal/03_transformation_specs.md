# 03. Time Transformation Specification

This document defines the deterministic time-conversion layer used after the agent decides that a message is actionable.

## 1. Purpose

The transformation layer converts source time into local time for each tracked participant.

It is intentionally deterministic. The LLM decides **whether** to act and **which points** to extract; the transformation layer decides **how** those points are converted.

## 2. Core Rule: UTC Pivot

All conversions must go through UTC.

```text
source local time -> aware datetime in source timezone -> UTC -> target timezone
```

Direct offset arithmetic between arbitrary user zones is not the contract.

## 3. Inputs

For each extracted point, the transformation layer needs:

- `original_time`
- `source_tz`
- list of target members with their `timezone`

`source_tz` resolution order:

1. if the point contains a city override and that city resolves successfully, use that timezone;
2. otherwise use the sender's stored timezone.

## 4. Reference Date

Time conversion is date-sensitive because DST and legal timezone rules depend on the date.

Current implementation anchors conversion to a reference date derived from the current runtime context. This is sufficient for same-day coordination, but relative-date interpretation remains partly upstream in the event-detection layer.

## 5. Output Contract

For each target timezone:

- return converted `HH:MM`,
- return day offset relative to source local date:
  - `0` same day
  - `+1` next day
  - `-1` previous day

The formatter is responsible for rendering markers such as `⁺¹` and `⁻¹`.

## 6. Data Integrity Rules

1. Persist only IANA timezone names.
2. Do not persist raw numeric offsets as the canonical user timezone.
3. Use `zoneinfo`/`tzdata` semantics for DST correctness.
4. If a timezone is invalid or missing, fail safely rather than guessing silently.

## 7. External Dependency Boundary

The transformation layer itself should not call network APIs.

It consumes already-resolved timezone names. City-to-timezone resolution belongs to the geo layer and should happen before deterministic conversion starts.

## 8. Rebuild Notes

If this module is rebuilt:

1. keep it pure and deterministic,
2. keep UTC as the conversion pivot,
3. keep source-timezone override per point,
4. keep day-offset reporting separate from formatting.
