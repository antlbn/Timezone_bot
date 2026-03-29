# 13. Configuration Reference

## 1. Purpose

This document defines the canonical configuration flags and their intended defaults for the MVP.

## 2. Configuration Sources

- `.env` stores secrets and platform tokens.
- `configuration.yaml` stores product, runtime, and operational settings.

## 3. `.env`

Expected keys:

```text
TELEGRAM_TOKEN=
DISCORD_TOKEN=
OPENAI_API_KEY=
GEMINI_API_KEY=
```

If a platform token is absent, that platform may be skipped at startup.

## 4. `configuration.yaml`

Top-level sections are grouped by responsibility.
Platform-specific sections are allowed only for genuinely platform-specific behavior that cannot be expressed in shared sections.

### 4.1 Bot Output

```yaml
bot:
  show_usernames: false
  reply_to_original_message: false
  show_event_title: false
  settings_cleanup_timeout_seconds: 30
```

Meaning:

- `show_usernames`: show grouped user names in formatted replies.
- `reply_to_original_message`: deliver conversion reply as a reply to the triggering message.
- `show_event_title`: render `event_title` only when explicitly returned by the LLM.
- `settings_cleanup_timeout_seconds`: TTL for short-lived bot messages in shared chats.

### 4.2 LLM

```yaml
llm:
  model: gpt-5
  temperature: 0.1
  base_url: null
  api_key_env: null
  fallback:
    enabled: false
    model: null
    temperature: 0.1
    base_url: null
    api_key_env: null
```

Meaning:

- `model`: selected model identifier.
- `temperature`: generation strictness / creativity balance.
- `base_url`: optional custom endpoint for compatible providers.
- `api_key_env`: optional environment variable name for the primary LLM API key.
- `fallback.enabled`: allow automatic retry on a secondary LLM.
- `fallback.model`: fallback model identifier.
- `fallback.temperature`: fallback generation setting.
- `fallback.base_url`: optional custom endpoint for fallback model.
- `fallback.api_key_env`: optional environment variable name for fallback API key.

### 4.3 Event Detection

```yaml
event_detection:
  onboarding_timeout_seconds: 120
  dm_onboarding_cooldown_seconds: 600
  max_message_age_seconds: 30
  max_message_hard_skip_chars: 2000
  log_prompts: false
```

Meaning:

- `onboarding_timeout_seconds`: frozen message expiry.
- `dm_onboarding_cooldown_seconds`: cooldown before re-inviting ignored users.
- `max_message_age_seconds`: stale-message guard.
- `max_message_hard_skip_chars`: safety limit for very long messages.
- `log_prompts`: debugging switch for LLM prompt logging.

Notes:

- There is no runtime master switch for event detection in the canonical MVP config.

### 4.4 Logging

```yaml
logging:
  level: INFO
```

### 4.5 Storage

```yaml
storage:
  inactive_user_retention_days: 30
```

### 4.6 Platform-Specific Sections

Optional sections such as `telegram:` or `discord:` may exist only for behavior that is truly platform-specific.

Examples:

- Discord ephemeral onboarding behavior,
- Telegram deep-link onboarding details.

## 5. Canonical Rules

- Specified defaults in this document are the canonical product defaults.
- Code should converge to these defaults.
- New config flags should be added here when they become part of the MVP contract.
- Flags that exist only as implementation leftovers should not remain undocumented.

## 5.1 Runtime Semantics

- Runtime code must read product configuration through the canonical config access layer rather than ad-hoc YAML reads inside feature modules.
- Cached configuration is allowed, but the cache must support explicit reset/reload in the same Python process.
- Reloading config must also clear dependent runtime caches whose values are derived from config, such as LLM attempt lists.
- Tests must be able to change `configuration.yaml` content or patch config/env accessors and observe the updated values without restarting the process.
- Stable config accessors are part of the internal runtime contract. When an accessor is renamed, all call sites must be updated in the same change or a backward-compatible alias must remain.

## 6. Non-Goals

- exhaustive vendor-specific environment options,
- advanced deployment tuning,
- post-MVP feature flags not used by the canonical runtime flow.
