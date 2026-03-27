# Spec Analysis: Current Gaps and Edge Cases

This file tracks open architectural risks in the current system. It should only describe live concerns, not contradictions from removed designs.

## 1. Thread Freshness After Long Inactivity

### Gap

Persisted LangGraph thread state currently has no freshness cutoff after long inactivity.

### Why it matters

After days or weeks of silence, old thread context may still influence the next reasoning pass even when that context is no longer useful.

### Risk

Stale semantic context can reduce update/publish quality after long gaps.

### Recommendation

Introduce a freshness policy for persisted threads or a summary/reset rule after inactivity.

## 2. Sender-Local Interpretation of Relative Dates

### Gap

Relative phrases such as "tomorrow" are anchored by message timestamp, but correctness depends on the sender's local timezone interpretation.

### Risk

If the sender is far from UTC or the chat spans extreme timezones, "tomorrow" may be interpreted relative to UTC rather than the sender's intended local date boundary.

### Recommendation

Make the sender-local anchor explicit in the LLM input contract and test cross-date-boundary cases.

## 3. Unknown `event_location`

### Gap

If the user specifies an event location that cannot be resolved, fallback behavior must stay explicit and safe.

### Risk

Silently assuming the sender timezone can produce a technically valid but semantically wrong conversion.

### Recommendation

Keep one explicit policy in the specs and code:

1. either abort the event,
2. or publish with a visible disclaimer.

## 4. Long Message Context Pressure

### Gap

The short-term history layer can still hold very large messages.

### Risk

A few oversized messages can distort prompt budgets and reduce agent quality.

### Recommendation

Enforce and document truncation rules for history snapshots and add tests around prompt-budget protection.

## 5. Telegram Membership Accuracy

### Gap

Telegram relies mainly on stored membership and bot-observed events. It does not have Discord's same-quality guild lifecycle signals.

### Risk

If the bot misses a leave event, stale members may remain in `chat_members` until someone removes them manually.

### Recommendation

Decide whether Telegram should remain "manual cleanup only" or gain a just-in-time verification strategy for high-confidence cases.
