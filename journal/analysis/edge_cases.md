# Spec Analysis: Gaps & Edge Cases

## 1. Contradictions & Discrepancies

### 1.1 `04_bot_logic.md` vs `14_llm_module.md` (New User Flow)
- **Gap**: In `04_bot_logic.md` (Sequence diagram and text), the new user flow says: "Bot asks: Reply with your city name:" and waits for a reply. However, `14_llm_module.md` says "LLM call is deferred... After the user's timezone is saved → replay the original message". 
- **The specific issue**: When a new user says "Meeting at 15:00", we defer the LLM call because we don't have their timezone. The bot uses ForceReply to ask for their city. What happens if other people send messages *while* the new user is answering? 
- **Edge case**: The deferred message (`"Meeting at 15:00"`) might lose its context if the chat moves on, or if the user takes 2 days to reply with their city, replying to a 2-day old time context doesn't make sense.
- **Recommendation**: Add a TTL (Time To Live) for deferred LLM calls. If the user doesn't onboard within X minutes (e.g., 10 mins), silently drop the deferred message.

### 1.2 `05_storage.md` vs `12_discord_integration.md` (User Exit)
- **Discord**: `12_discord_integration.md` explicitly states that stale users are removed automatically *at the moment of time mention* (by checking if they are still in the `guild.members` list).
- **Telegram**: `05_storage.md` relies entirely on the `ChatMemberUpdated` event to remove users.
- **The gap**: In Telegram, if the bot is briefly offline or misses the `ChatMemberUpdated` webhook, a user who left the chat will remain permanently stuck in the `chat_members` table, and will endlessly receive time conversions for a chat they aren't in.
- **Recommendation**: Implement the same Just-In-Time (JIT) check for Telegram as we do for Discord. Before formatting the response in Telegram, verify via `bot.get_chat_member(chat_id, user_id)` if the user is still there, and auto-delete if they left.

## 2. Unhandled Edge Cases

### 2.1 The "Anchor Time" vs "Source Time" Ambiguity
- When matching a relative time like "завтра" (tomorrow), we use `anchor_timestamp_utc` (the timestamp of the message).
- **Edge case**: If `user A` is in Tokyo (UTC+9) and `user B` is in Honolulu (UTC-10), it might already be "tomorrow" (e.g., Tuesday) for A, but still "today" (Monday) for B. 
- The LLM parses "завтра" relative to the message's `timestamp_utc` (which is absolute). But "завтра" meant *Tuesday* to the sender in Honolulu, while the UTC date might already be Tuesday, moving the LLM's interpretation to *Wednesday*.
- **Recommendation**: The `anchor_timestamp` passed to the LLM should ideally be localized to the **sender's timezone**, so the LLM knows what "today" means to the sender.

### 2.2 Geocoding Fallbacks & `event_location`
- `14_llm_module.md`: "If geocoding of `event_location` fails... fall back to sender's DB timezone and log a warning."
- **UX Edge Case**: If someone types "в 15:00 по марсу" (at 15:00 Mars time), the bot falls back to the sender's timezone (e.g., Berlin). The bot will reply with translated times based on Berlin time, *without telling anyone that it ignored "Mars"*. This leads to fundamentally incorrect time coordination because the sender meant Mars (or completely made it up), but the bot silently assumed Berlin.
- **Recommendation**: If `event_location` geocoding fails, the bot should either abort the trigger entirely, OR include a disclaimer in the output: `⚠️ Unknown location "Mars", assuming Berlin time.`

### 2.3 LLM Output Formatting Error (JSON Schema Failure)
- What happens if the LLM output is not valid JSON, or misses a required field (e.g. `confidence` is missing)?
- We have tests for this, but the runtime behavior is not explicitly defined in the logic specs.
- **Recommendation**: explicitly state in `14_llm_module.md` that JSON schema validation failures result in `trigger=false` (fail-safe silence).

### 2.4 Multi-Message Context Limits
- According to the new deque rules, `extended_context_messages: 3`.
- What if someone forwards a massive wall of text containing 10,000 words? Putting 3 of those into the LLM context might exceed the token limit of the model.
- **Recommendation**: Add a hard character limit per message when adding to the deque (e.g., truncate `text` to the first 500 chars).

### 2.5 Discord Modal Timeout
- `12_discord_integration.md`: Discord un-registered user gets a button -> opens modal -> answers.
- If the bot restarts while the user is staring at the modal, submitting it will fail (Interaction Failed).
- The deferred message replay logic (`replay original message`) relies on in-memory state mapping the interaction to the original message. If the bot restarts, this memory is lost.
- **Recommendation**: Document that deferred messages are *best-effort in-memory only*. If the bot restarts, the onboarding still completes (DB saves timezone), but the original message won't be replayed.
