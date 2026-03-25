# Spec Analysis: Current Gaps and Edge Cases

This file tracks open architectural risks in the current system. It should only describe live concerns, not contradictions from removed designs.

## 1. High-Load Ordering Semantics

### Gap

Message handling is serialized per chat, but `append_to_history(...)` happens before the chat lock is acquired.

### Why it matters

This means the system guarantees serialized execution, but not a perfectly atomic "append history + snapshot + execute" sequence under burst load.

### Risk

In a fast burst of messages, context snapshots may be slightly less intuitive than a human would expect, even though thread-state corruption is still prevented.

### Recommendation

If load becomes a real problem, consider moving history append and snapshot capture inside the per-chat lock and add burst-ordering tests.

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
