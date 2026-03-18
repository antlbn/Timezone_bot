# Timezone Bot: UX & Onboarding Specification

This document defines the user experience guidelines and implementations for the Timezone Bot across different platforms.

## 1. Core Philosophy: Zero-Friction & Context Preservation

> [!TIP]
> **The Golden Rule:** Users should never be forced to interrupt their conversation flow to interact with the bot.

- **Graceful Handling**: The bot must gracefully handle missing data (like a missing timezone) without throwing errors or breaking the user's flow.
- **Background Queuing**: If the bot needs setup info from a user, it must queue their messages in the background, allow them to complete the setup, and then seamlessly process the backlog.
- **Pristine Chats**: Bot configuration and utility messages should leave zero trace in active chat histories once they are no longer needed.

---

## 2. Current Implementation (As-Is)

### 2.1 Telegram User Experience
Telegram lacks native Ephemeral Messages and Modals for group chats. We use **DM-based onboarding via deep links** to keep the group chat pristine while conducting the full setup dialogue in the bot's private messages.

#### Onboarding Flow
1. **Trigger:** A new user (not in the database, OR lacking a timezone without explicitly declining) sends *any* text in a group chat.
   - *Note: The bot checks the DB cache first, entirely bypassing the LLM to save latency and costs.*
2. **Queuing:** The message is instantly saved to an in-memory pending queue. Further processing (including LLM analysis) is paused.
3. **Cooldown Check:** The bot checks if a DM invite was already sent within the `dm_onboarding_cooldown_seconds` window (default: 600s = 10 min). If so, the message is only queued — no new invite is sent.
4. **Invite:** If cooldown allows, the bot sends a minimal message to the group:
   > "Hi {Name}! Tap the button to quickly set up your timezone 👇"
   > **Button:** `[📍 Set up timezone]` ← This is a **URL button** (deep link to `t.me/bot?start=onboard_{userId}_{chatId}`)
5. **Auto-Cleanup:** The invite message is automatically deleted from the group after `settings_cleanup_timeout_seconds` (default: 10s).
6. **DM — Accept Path:**
   - User clicks the URL button → Telegram opens the bot's private chat.
   - The bot sends: *"Hi {Name}! What city are you in?"* with a `[✖️ No thanks]` inline button.
   - The user types their city. If invalid, the bot asks for a retry or manual time — all in the DM.
   - On success: timezone saved, confirmation sent in DM, and all pending messages are processed by the LLM with results sent back to the **original group chat**.
7. **DM — Decline Path (`[✖️ No thanks]`):**
   - The user is saved to the DB as `onboarding_declined=True` to prevent future nagging.
   - Bot responds in DM: *"Got it! If you change your mind, use /tb_settz in any chat."*
   - Pending messages are processed by the LLM (without timezone context).
8. **Ignore / Abandon Path:**
   - If the user doesn't open the DM, or opens it but doesn't complete setup:
     - Pending messages expire after `onboarding_timeout_seconds` (default: 60s).
     - The bot won't re-invite until `dm_onboarding_cooldown_seconds` passes (default: 10 min).
     - On the user's next message (after cooldown), a new invite is sent.
9. **Security:** The deep-link payload contains the user's ID. If a different user tries to use the link, the bot responds: *"This link is not for you! 😊"*

#### ⭐ Auto-Cleanup for Settings Dialogs
To keep chat histories perfectly clean, **all** bot configuration commands use an automated background cleanup system.

> [!IMPORTANT]
> **Cleanup Rules:**
> - **`/tb_help`, `/tb_me`, `/tb_members`:** Both the user's command message and the bot's response are automatically deleted after exactly **10 seconds**.
> - **`/tb_settz`, `/tb_remove`:** The user's command message is deleted immediately. The bot's interactive prompt is deleted the moment the user finishes or cancels the flow, OR automatically after **10 seconds** if they ignore it.
> - **Onboarding invite:** Auto-deleted from the group after `settings_cleanup_timeout_seconds`.

---

### 2.2 Discord User Experience
Discord offers native Ephemeral Messages and Modals, allowing for a strictly targeted UX without cluttering the chat history at all.

#### Onboarding Flow
1. **Trigger:** A new user mentions a time in a guild.
2. **Queuing:** The message is queued, similar to Telegram.
3. **Prompt:** The bot replies to the user, mentioning them directly:
   > "{Name}, set your timezone to convert times!"
   > **Button:** `[Set Timezone]`
4. **Accept Path (Modals):**
   - User clicks the button. (Other users see an ephemeral "Not for you" message if they click).
   - A Discord Modal pops up: *"Set Your Timezone"* with a text input field for *"Your City"*.
   - User submits the form.
   - The bot processes the city, saves the timezone, and releases the queued messages for conversion.
5. **Fallback:**
   - If the city is invalid, the bot responds with an ephemeral message containing a `FallbackView`: `[Try Again]` (reopens city modal) or `[Enter Time]` (opens a modal to enter manual time).

---

## 3. Future Directions
*(Ideas for evolving the onboarding experience based on feedback and conceptual design).*

- **Smart re-invite timing:** Instead of a fixed cooldown, track user activity patterns and invite at optimal times.
- **Multi-chat awareness:** If a user has already set their timezone in one group, skip onboarding in other groups.

---

## 4. Historical Context: What We Tried & Discarded

> [!NOTE]
> This section documents past design decisions to prevent repeating old mistakes.

| Feature Attempted | Why We Discarded It | The Solution We Built |
| :--- | :--- | :--- |
| **Strict ForceReply in Telegram** | Users frequently ignored or forgot to use the Telegram reply function. They would just type "London" in the chat, leading to a locked `FSMContext` state. | Relaxed the check. If the user is in the `waiting_for_city` state, the bot accepts their next text message as the city input. |
| **Leaving Bot Prompts in the Chat** | In active Telegram groups, leaving "What city are you in?" and the user's "London" messages severely cluttered the conversation with onboarding noise. | Implemented **Auto-Cleanup**. The bot actively deletes inline buttons, `ForceReply` prompts, and the user's setup submission messages. |
| **Inline Buttons + ForceReply in Group Chat (v1)** | Even with auto-cleanup, the onboarding dialogue (buttons, city input, fallback prompts) polluted the group chat. Multiple messages were exchanged in the shared space before cleanup could run. | Moved the entire onboarding dialogue to **DM via deep links**. The group chat only ever sees a single auto-deleting invite message. |
