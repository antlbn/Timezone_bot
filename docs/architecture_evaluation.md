# Architecture Evaluation & Principles (Timezone Bot)

Below are the answers to three key architectural questions, along with a general evaluation of the codebase.

## 1. What is the Domain, what is the Transport?

*   **Domain (Core)** — The heart of the application, pure business logic. Located in `src/core`. 
    *   **Includes:** Platform-agnostic data structures (`InputData`, `MessageContext`, `MessageDecision`), message processing pipeline (`GuardStage`, `DetectionStage`, `FormatStage`, etc.), and orchestration services (`MessageProcessingService`, `OnboardingCompletionUseCase`).
    *   **Key Feature:** The domain knows absolutely nothing about Telegram, Discord, SQLite, or specific LLM providers. It communicates with the outside world exclusively through abstract interfaces (Ports).
*   **Transport (Infrastructure / Adapters)** — Input/output mechanisms linking the domain to the real world. Located in `src/adapters`.
    *   **Inbound:** `aiogram` (Telegram) and `discord.py` (Discord) frameworks. They listen to Webhooks/Polling, convert JSON to `InputData` domain objects, and invoke domain services.
    *   **Outbound:** Port implementations. Sending messages (`TelegramCommandExecutor`), DB access (`SQLiteUserRepository`), LLM calls (`LiteLLMDetectionAdapter`), and getting system time (`RealTimeAdapter`).

## 2. Who owns the state and how is it destroyed?

The project has two fundamentally different types of state:

*   **Persistent State:**
    *   *What it is:* User settings, timezones, declined onboarding flags, chat associations.
    *   *Owner:* Repositories (e.g., `SQLiteUserRepository`).
    *   *Lifecycle:* Exists permanently. Updated upon onboarding completion or decline, never destroyed (except manual DB cleanup).
*   **Workflow State (Onboarding):**
    *   *What it is:* Saved original message (`pending_message`) while the user selects a timezone, and spam protection (`chillout_state`).
    *   *Owner:* In-memory repositories (`MemoryOnboardingPendingRepository`).
    *   *Lifecycle:*
        *   **Creation:** When time is detected for an unconfigured user.
        *   **Explicit Destruction:** `OnboardingCompletionUseCase` explicitly deletes the message from memory after "replaying" it with the new timezone, or if the user clicks "Cancel".
        *   **Implicit Destruction (TTL/Staleness):** During a replay attempt, the pipeline checks age via `TimePort`. If `age > max_age_fresh_secs`, the message is discarded without reply and the record is cleared. Also completely destroyed on container restart.

## 3. What makes decisions, what executes them?

The architecture strictly follows the **Functional Core, Imperative Shell** (Pipeline + Command) pattern.

*   **Decision Making:**
    *   Done exclusively inside the **Domain**. 
    *   Pipeline stages (`DecisionStage`) analyze the enriched `MessageContext` and form a `MessageDecision` (e.g., "needs onboarding" or "reply with text X"). 
    *   Services (`MessageProcessingService`) take this decision and turn it into a **Command** pattern (`SendReply`, `ShowOnboarding`).
    *   *Important:* The domain only forms intent, it makes zero network calls.
*   **Execution:**
    *   Done in the external layer (**Adapters**).
    *   `DeliveryService` routes generated commands to the correct `CommandExecutor` based on the platform.
    *   The executors take the `SendReply` command and perform the actual HTTP request to the messenger API.

---

## Response to Previous Review Critique

The current architecture is a direct response to the critique of the previous (MVP) version. Here is how the three fundamental issues were resolved:

### 1. No domain layer and too many `dict`s
**Was:** Behavior instead of interfaces, `dict` used as the main data transfer method, blurred boundaries between transport and logic.
**Now:** 
* A `src/core/domain/` folder was added containing strict types (`UserProfile`, `Platform`, `DetectionResult`, `MessageContext`).
* A strict Boundary was established via interfaces (`src/ports/`). The domain no longer accepts raw LLM responses or DB rows — adapters must parse `aiosqlite.Row` or LLM JSON into domain dataclasses *before* passing them to the pipeline.

### 2. Python + dict + defensive style
**Was:** Defensive programming with `.get(key, default)`, weak typing, no schema confidence.
**Now:**
* Total rejection of passing dictionaries between layers.
* Using `dataclasses` (and `pydantic` at the LLM parsing layer) guarantees field presence. Optional fields are explicitly marked with `| None`. 
* Type drift is now caught by static analysis (`ruff`).

### 3. Forced MVP without phase transition
**Was:** Module-level global variables, tight coupling, making it hard to add a second adapter (Discord).
**Now:**
* A **full phase transition** was executed. 
* **Dependency Injection** was introduced: all dependencies are assembled in the container inside `main.py` (Composition Root).
* Global variables were completely destroyed.
* The project proved its orthogonality: adding the Discord adapter required zero changes in `src/core`, as the core is abstracted from the transport.
