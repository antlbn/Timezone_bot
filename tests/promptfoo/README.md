# LLM Evaluation with Promptfoo

This directory contains evaluation tests for the LLM event detection engine.

## Configuration

- `promptfooconfig.yaml`: Main configuration file.
- `cases.yaml`: Test cases with variables and assertions.
- `prompt.txt`: The full system prompt + user message template.

## Execution

### Run Evaluation
To run the tests against your local Ollama model:
```bash
npx --yes promptfoo@0.119.0 eval -c tests/promptfoo/promptfooconfig.yaml
```

### View Results
To open the results in a local web dashboard:
```bash
npx promptfoo@0.119.0 view -y
```

> [!NOTE]
> We use version `0.119.0` to avoid compatibility issues with ESM/CommonJS imports in the latest versions on some environments.
