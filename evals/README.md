# Prompt Evaluation Lab

This directory is a small laboratory for comparing prompt variants for the detection module.

The production contract is the source of truth. Experimental prompts may differ in wording and strategy, but they must all use the same runtime variables and the same output schema.

## What is here

- `prompts/` — alternative system prompt variants for comparison
- `cases_mini.yaml` — fast regression subset
- `cases.yaml` — broader experimental suite
- `promptfooconfig.yaml` — main promptfoo config
- `promptfooconfig_smoke.yaml` — quick smoke config

## Required runtime variables

All prompts in this folder must use the same placeholders:

- `{{timestamp}}`
- `{{text}}`

And the same message framing:

```text
CURRENT TIME (UTC): {{timestamp}}
CURRENT MESSAGE:
{{text}}
```

## Required output contract

All prompts in this folder must target the current detection schema:

```json
{
  "time_mentioned": true,
  "points": [
    {
      "time": "HH:MM",
      "tz_city": null,
      "event_title": null,
      "am_pm_clear": true
    }
  ]
}
```

Notes:

- `time_mentioned` is the top-level boolean flag
- `tz_city` is the message-level timezone reference for that point
- `am_pm_clear` is required for every point
- experimental prompts must not fall back to the old `event/city` schema

## How to run

Install promptfoo:

```bash
npm install -g promptfoo
```

Set model API keys in your environment or in the repo `.env`.

Run the quick subset:

```bash
cd evals
promptfoo eval -c promptfooconfig_smoke.yaml
```

Run the broader suite:

```bash
cd evals
promptfoo eval -c promptfooconfig.yaml
```

Open results:

```bash
promptfoo view
```

## Practical workflow

1. Duplicate or edit a prompt in `prompts/`
2. Keep placeholders and output schema unchanged
3. Run `cases_mini.yaml` first
4. Run `cases.yaml` when the prompt survives the mini set
