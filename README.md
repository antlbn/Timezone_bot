# Timezone Bot

Timezone Bot detects time mentions in Telegram and Discord group chats and replies with converted local times for known chat members.

## What It Does

- Watches regular chat messages.
- Uses an LLM to detect time references in the current message.
- Resolves the source timezone from the message or from the sender profile.
- Converts the detected time for known members of the same chat.
- Starts onboarding when a user without a configured timezone mentions time.

## Example

```text
User: Let's sync tomorrow at 15:00
Bot: It is 15:00 Berlin, 09:00 New York
```

Reply formatting is configurable through `configuration.yaml`.

## Architecture

The project uses platform adapters around a shared application/core flow.

- Telegram and Discord adapters receive incoming messages.
- `MessageProcessingService` runs the fresh-message workflow.
- `Pipeline` performs detection, timezone resolution, member hydration, formatting, and decision-making.
- Delivery executors send replies or onboarding prompts back to the platform.

Current fresh-message pipeline:

```text
GuardStage
-> AgingStage
-> DetectionStage
-> GeoResolveStage
-> HydrationStage
-> FormatStage
-> DecisionStage
```

The pipeline returns `MessageContext` with a final `MessageDecision`. It does not send messages and does not write pending onboarding state directly.

## Run Locally

```bash
cp env.example .env
uv sync
./run.sh
```

Python 3.12+ is required.

## Documentation

- [docs/setup.md](docs/setup.md) — setup, runtime configuration, and tests
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — current architecture and message flow
- [docs/decisions.md](docs/decisions.md) — design decisions and accepted trade-offs
- [docs/archive/](docs/archive/) — historical notes
