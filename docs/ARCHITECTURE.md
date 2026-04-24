# Architecture

This document describes the current implementation, not a target-state design.

## Overview

Timezone Bot is a Telegram and Discord bot with shared message-processing logic.

At a high level:

- inbound adapters receive platform events
- application services orchestrate workflows
- the core pipeline evaluates a message and produces a decision
- outbound adapters implement storage, detection, geocoding, and delivery

The project follows a hexagonal style with a shared core, but the current implementation is pragmatic rather than doctrinaire.

## Main Components

### Inbound Adapters

- `src/adapters/inbound/telegram/`
- `src/adapters/inbound/discord/`

Responsibilities:

- translate platform events into `InputData`
- call application services
- expose platform-specific onboarding UI and commands

### Application Services

- `MessageProcessingService`
- `OnboardingPromptService`
- `OnboardingCompletionUseCase`
- `ProfileService`

Responsibilities:

- run the fresh-message flow
- register observed users and chat membership
- store pending onboarding messages
- complete onboarding and replay the latest pending message
- route delivery commands to platform executors

### Core Pipeline

- `src/core/pipeline/pipeline.py`
- `src/core/pipeline/stages.py`

Responsibilities:

- validate incoming messages
- detect time references
- resolve explicit timezone cities
- load sender and member context
- format the reply text
- produce a final decision

### Outbound Adapters

- `SQLiteStorage`
- `OpenAIDetector`
- `NominatimGeo`
- `MemoryOnboardingPending`
- `MemoryOnboardingChilloutState`
- platform command executors

## Message Flow

Fresh message flow:

```text
Telegram/Discord event
-> InputData
-> MessageProcessingService
-> fresh Pipeline
-> MessageDecision
-> application-side effects
-> SendReply / ShowOnboarding
-> DeliveryService
-> TelegramCommandExecutor / DiscordCommandExecutor
```

Replay flow after onboarding:

```text
OnboardingCompletionUseCase
-> resolve submitted city
-> persist user timezone
-> load latest pending message
-> replay Pipeline
-> MessageDecision
-> SendReply
-> DeliveryService
```

## Pipeline

Fresh pipeline order:

```text
GuardStage
-> AgingStage
-> DetectionStage
-> GeoResolveStage
-> HydrationStage
-> FormatStage
-> DecisionStage
```

Replay pipeline order:

```text
HydrationStage
-> FormatStage
-> DecisionStage
```

### Stage Responsibilities

| Stage | Responsibility |
|---|---|
| `GuardStage` | Drop bot messages, empty messages, and overlong messages |
| `AgingStage` | Drop stale fresh messages |
| `DetectionStage` | Call the LLM detector and stop early if no time was found |
| `GeoResolveStage` | Resolve explicit `tz_city` values into IANA timezone names |
| `HydrationStage` | Load sender profile and known chat members with configured timezones |
| `FormatStage` | Produce reply text from detected time points and hydrated context |
| `DecisionStage` | Produce final `MessageDecision` |

## Decision Model

The pipeline does not return platform commands.

It returns an updated `MessageContext`. The final outcome is stored in `MessageContext.decision` as `MessageDecision`.

`MessageDecision` may contain:

- `reply_text`
- `pending_message`
- `needs_onboarding`
- `ignore`

This split is intentional in the current codebase:

- the pipeline decides what the outcome of message evaluation is
- application services perform side effects and build delivery commands

## Commands And Delivery

The current delivery command set is small:

- `SendReply`
- `ShowOnboarding`

These commands are created in application services, not inside the pipeline.

Execution flow:

```text
MessageDecision
-> MessageProcessingService / OnboardingCompletionUseCase
-> list[Command]
-> DeliveryService
-> platform executor
```

`BaseCommandExecutor` provides dispatch logic, and platform executors implement platform-specific behavior for:

- sending replies
- showing onboarding prompts

There is no `SavePending` command in the current implementation. Pending onboarding state is stored through `OnboardingPromptService`.

## Composition Root

`src/main.py` loads configuration, creates platform clients, and delegates object wiring to `build_container()` in `src/container.py`.

The container currently wires:

- repositories
- LLM detector
- geocoder
- time adapter
- pending onboarding stores
- pipelines
- application services
- delivery executors

This is the practical composition root of the application.

## Configuration Boundaries

The runtime configuration is split across:

- `.env` for tokens and optional LLM overrides
- `configuration.yaml` for logging, bot behavior, detection limits, and LLM defaults

Settings that form clear responsibility boundaries are grouped in typed objects such as:

- `LLMConfig`
- `BotSettings`
- `LoggingConfig`
- `TelegramConfig`

Single-purpose values may remain as plain fields on `AppConfig`.

## Current Limitations

- Detection is one-shot and uses only the current message.
- Known members are collected passively from observed activity.
- Pending onboarding state is stored in memory and is lost on process restart.
- Replay handles only the latest pending message per user/platform pair.
- The current implementation is single-process oriented.

## Notes On Accuracy

This file intentionally documents the code as it exists now.

It does not assume:

- `CommandFactory`
- `SavePending` / `NoOp` commands
- pipeline-owned side effects
- a richer domain model than the current implementation
