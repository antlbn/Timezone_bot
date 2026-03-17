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
Telegram lacks native Ephemeral Messages (visible only to one user) and Modals (popup forms) for group chats. We use a combination of Inline Keyboards, Force Replies, and aggressive Auto-Cleanup to simulate a clean UX.

#### Onboarding Flow
1. **Trigger:** A new user (not in the database, OR lacking a timezone without explicitly declining) sends *any* text containing a potential time format. 
   - *Note: The bot checks the DB cache first, entirely bypassing the LLM to save latency and costs.*
2. **Queuing:** The message is instantly intercepted and added to an in-memory pending queue. Further processing (including LLM analysis) is paused.
3. **Prompt:** The bot sends an interactive message to the group: 
   > "Hi {Name}! I can help coordinate times in this chat. To show your local time to others, I need to know your city."
   > **Buttons:** `[📍 Set city]` `[✖️ No thanks]`
4. **Security:** If a different user clicks the button, Telegram shows them a native popup alert: *"This button is not for you! 😊"* The bot ignores the click.
5. **Accept Path (`[📍 Set city]`):**
   - The bot deletes the button message.
   - The bot targets the user with a `ForceReply(selective=True)`: *"Great {Name}! What city are you in?"*
   - The user types their city by replying to the prompt.
   - The bot deletes both the user's city message and its own prompt to keep the group pristine.
   - The queued message is processed by the LLM (now with timezone context) and the converted time is sent to the chat.
6. **Decline Path (`[✖️ No thanks]`):** 
   - The bot deletes its prompt message.
   - The user is saved to the DB as `onboarding_declined=True` to prevent future nagging.
   - The queued message is processed by the LLM. If the user explicitly wrote a timezone (e.g., *"15:00 GMT"*), it succeeds. Otherwise, it fails silently.
7. **Cancellation & Fallback:**
   - If the user types an invalid city, the bot falls back and asks for time or city again (`waiting_for_time`). It does not crash the flow.

#### ⭐ Auto-Cleanup for Settings Dialogs
To keep chat histories perfectly clean, **all** bot configuration commands use an automated background cleanup system.

> [!IMPORTANT]
> **Cleanup Rules:**
> - **`/tb_help`, `/tb_me`, `/tb_members`:** Both the user's command message and the bot's response are automatically deleted after exactly **10 seconds**.
> - **`/tb_settz`, `/tb_remove`:** The user's command message is deleted immediately. The bot's interactive prompt is deleted the moment the user finishes or cancels the flow, OR automatically after **10 seconds** if they ignore it.

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

- **Remove "Relaxed Replies" in Telegram.** Currently, the bot has a relaxed check that tries to accept a user's city input even if they don't explicitly "Reply" to the `ForceReply` prompt. This might cause unexpected behaviors if they just keep chatting normally. This should be reviewed and potentially reverted to strictly require a reply.

---

## 4. Historical Context: What We Tried & Discarded

> [!NOTE]
> This section documents past design decisions to prevent repeating old mistakes.

| Feature Attempted | Why We Discarded It | The Solution We Built |
| :--- | :--- | :--- |
| **Strict ForceReply in Telegram** | Users frequently ignored or forgot to use the Telegram reply function. They would just type "London" in the chat, leading to a locked `FSMContext` state. | Relaxed the check. If the user is in the `waiting_for_city` state, the bot accepts their next text message as the city input. (See *Future Directions*). |
| **Leaving Bot Prompts in the Chat** | In active Telegram groups, leaving "What city are you in?" and the user's "London" messages severely cluttered the conversation with onboarding noise. | Implemented **Auto-Cleanup**. The bot actively deletes inline buttons, `ForceReply` prompts, and the user's setup submission messages. |
| **Direct Messages (DMs) for Onboarding** | Forcing the user to go to the Bot's private DMs via deep-link (e.g., `t.me/bot?start=settz`) forces a hard, disruptive context switch out of their active conversation. | The current inline flow with Auto-Cleanup achieves a similarly "clean" chat result without forcing the user to leave their group. |
