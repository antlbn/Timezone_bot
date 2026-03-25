# Timezone Bot: UX & Onboarding Specification

This document defines the user experience guidelines and implementations for the Timezone Bot across different platforms.

## 1. Core Philosophy: Zero-Friction & Context Preservation

> [!TIP]
> **The Golden Rule:** Users should never be forced to interrupt their conversation flow to interact with the bot.

- **Graceful Handling**: The bot must gracefully handle missing data (like a missing timezone) without throwing errors or breaking the user's flow.
- **Background Prompting**: If the bot needs setup info from a user, it prompts them once and then relies on an invite cooldown to avoid repeated nagging. It does not queue or replay old chat messages.
- **Pristine Chats**: Bot configuration and utility messages should leave zero trace in active chat histories once they are no longer needed.

---

## 2. Current Implementation (Target Behavior)

Since the project moved from the old "single-pass LLM + local history" model to a **LangGraph agent with persisted thread state**, onboarding now has one critical architectural rule:

> **Before the user completes onboarding, the bot may run detection, but it must not leave a fake "published event" trace in the real chat thread memory.**

That means the first pass for an unregistered user is a **detection-only pass**:
- it may use recent context to decide whether the message is actionable,
- it may trigger an onboarding invite if cooldown allows,
- but it must **not** persist a tool result as if the chat reply was already published.

After setup completes, the bot starts handling the user's **next** messages normally.

### 2.1 Telegram User Experience
Telegram lacks native Ephemeral Messages and Modals for group chats. We use **DM-based onboarding via deep links** to keep the group chat pristine while conducting the full setup dialogue in the bot's private messages.

#### Onboarding Flow
1. **Trigger:** A new user (timezone missing) sends a message in a group. The bot performs a **detection-only LangGraph pass**:
   - If **no time event** is detected → the message remains only as ordinary chat context; onboarding is not shown.
   - If **time event** is detected → onboarding is triggered (Lazy Onboarding), but no chat reply is published yet.
2. **Cooldown Check:** The bot checks if a DM invite was already sent within the `dm_onboarding_cooldown_seconds` window (default: 600s). If so, the message is only queued — no new invite is sent.
4. **Invite:** If cooldown allows, the bot sends a minimal message to the group:
   > "Hi {Name}! Tap the button to quickly set up your timezone 👇"
   > **Button:** `[📍 Set up timezone]` ← URL button to `t.me/bot?start=onboard_{userId}_{chatId}`
5. **Auto-Cleanup:** The invite message is automatically deleted from the group after `settings_cleanup_timeout_seconds` (default: 10s).
6. **DM — Welcome Step:**
   - User clicks the URL button → Bot opens private chat.
   - The bot sends a concise greeting: *"What am I"*, *"How to use me"*, and two buttons: `[📍 Set up timezone]` and `[🔒 Data Privacy]`.
   - **Data Privacy:** Shows information about data storage and the 30-day auto-deletion policy.
7. **DM — City Prompt:**
   - On clicking `[📍 Set up timezone]`, the bot sends detailed instructions: *"Tell me your city... e.g. Paris, France or Paris, Texas, USA."*
   - The user types their city.
   - On success: timezone is saved, confirmation is sent in DM, and the bot starts working from the user's **next** chat message.
8. **DM — Decline / Ignore:**
   - If the user declines, they are marked as `onboarding_declined=True`.
   - If they ignore or abandon the flow, nothing is replayed later; the bot will only re-invite after the onboarding cooldown expires and a new actionable message appears.
9. **Security:** The deep-link payload is validated. If another user tries to use it, the bot ignores it.
10. **Memory boundary:** The initial detection-only pass is **not allowed** to create a fake published event in the persisted LangGraph chat thread. The real thread history is updated only during the replay after successful setup.

#### ⭐ UX Principles & Cleanup Rules
- **Non-disruptive**: No intrusive dialogs in the group. All setup happens "behind the scenes" in DM.
- **No Backlog Replay**: Messages written before the user finishes setup are not replayed later. Once onboarding completes, the bot starts from the next message.
- **Clean Chats**: All system messages have a TTL.
  - **Group Invites:** 10s (`settings_cleanup_timeout_seconds`)
  - **Help / Me / Members:** 10s (both command and reply)
  - **DM Context:** Important info (Welcome, City Prompt) **stays** for reference; transient commands (like `/tb_help` inputs) are cleaned up.

#### 🛠️ Configurable Timers (`configuration.yaml`)
| Parameter | Default | Description |
| :--- | :--- | :--- |
| `settings_cleanup_timeout_seconds` | 30s | TTL for system/help messages in groups. |
| `dm_onboarding_cooldown_seconds` | 10m | Cooldown to prevent spamming invitations. |
| `max_message_age_seconds` | 30s | How old a message can be before the bot ignores it (preventing catch-up spam). |

#### Runtime Notes

- **Invite cooldown storage**: `src/storage/pending.py`
- **Telegram replay path**: `src/commands/settings.py`
- **Discord replay path**: `src/discord/commands.py`
- **Detection-only pass**: `src/event_detection/detector.py`
- **Real publish pass**: `src/event_detection/__init__.py` + `src/event_detection/graph.py`

---

## 3. Lazy Onboarding Flow Diagram

```mermaid
flowchart TD
    A[Incoming group message] --> B{User has timezone?}
    B -- YES --> C[Normal process_message pass<br/>real publish/update allowed]
    B -- NO --> D[Detection-only LangGraph pass<br/>no real publish side effects]

    D -- No event --> E[Stop<br/>keep only ordinary context]
    D -- Event detected --> F[Check onboarding invite cooldown]

    F --> G[Send onboarding invite]
    G --> H{User action}

    H -- Completes setup --> I[Process next messages normally]
    H -- Declines --> J[Stop auto-invites]
    H -- Ignores/abandons --> K[Wait for next actionable message<br/>after cooldown]
```

---

### 2.2 Discord User Experience
Discord offers native Ephemeral Messages and Modals, allowing for a strictly targeted UX without cluttering the chat history at all.

#### Onboarding Flow
1. **Trigger:** A new user mentions a time in a guild.
2. **Detection-only pass:** The bot checks the message with the agent, but before registration it must not persist a fake publish result into the real chat thread.
3. **Prompt:** If cooldown allows, the bot replies to the user, mentioning them directly:
   > "{Name}, set your timezone to convert times!"
   > **Button:** `[Set Timezone]`
5. **Accept Path (Modals):**
   - User clicks the button. (Other users see an ephemeral "Not for you" message if they click).
   - A Discord Modal pops up: *"Set Your Timezone"* with a text input field for *"Your City"*.
   - User submits the form.
   - The bot processes the city, saves the timezone, and starts converting **future** messages.
6. **Fallback:**
   - If the city is invalid, the bot responds with an ephemeral message containing a `FallbackView`: `[Try Again]` (reopens city modal) or `[Enter Time]` (opens a modal to enter manual time).

---

## 4. Future Directions
- **Smart re-invite timing:** Instead of a fixed cooldown, track user activity patterns and invite at optimal times.
- **Multi-chat awareness:** If a user has already set their timezone in one group, skip onboarding in other groups.

---

## 5. Historical Context: What We Tried & Discarded

> [!NOTE]
> This section documents past design decisions to prevent repeating old mistakes.

| Feature Attempted | Why We Discarded It | The Solution We Built |
| :--- | :--- | :--- |
| **Strict ForceReply in Telegram** | Users frequently ignored or forgot to use the Telegram reply function. They would just type "London" in the chat, leading to a locked `FSMContext` state. | Relaxed the check. If the user is in the `waiting_for_city` state, the bot accepts their next text message as the city input. |
| **Leaving Bot Prompts in the Chat** | In active Telegram groups, leaving "What city are you in?" and the user's "London" messages severely cluttered the conversation with onboarding noise. | Implemented **Auto-Cleanup**. The bot deletes temporary onboarding artifacts in group flows; the DM onboarding path leaves only the minimal invite in the group. |
| **Inline Buttons + ForceReply in Group Chat (v1)** | Even with auto-cleanup, the onboarding dialogue (buttons, city input, fallback prompts) polluted the group chat. Multiple messages were exchanged in the shared space before cleanup could run. | Moved the entire onboarding dialogue to **DM via deep links**. The group chat only ever sees a single auto-deleting invite message. |
| **Persisting fake publishes before setup** | After the switch to LangGraph, a detection-only pass could accidentally leave a trace in the real chat thread as if the event had already been published. That breaks future update semantics. | Detection before setup must run in an **isolated ephemeral thread**. No old message is replayed after setup; the bot simply starts from the next user message. |
