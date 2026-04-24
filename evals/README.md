# LLM Prompt Evaluation Suite

This directory contains the evaluation suite for the Timezone Bot detection prompts. It uses [promptfoo](https://www.promptfoo.dev/) to test different prompts against a set of real-world and edge-case scenarios.

## 📁 Structure

- `promptfooconfig.yaml`: Main configuration file (models, prompts, settings).
- `cases.yaml`: Comprehensive test suite (50+ scenarios).
- `prompts/`: Collection of system prompts under test.
- `providers/`: Custom Python scripts for structured output evaluation.

## 🚀 How to Run

### 1. Install promptfoo
You need Node.js installed. Then run:
```bash
npm install -g promptfoo
```

### 2. Set API Keys
Ensure you have the required API keys in your environment:
```bash
export GOOGLE_API_KEY='your_key'
export GROQ_API_KEY='your_key'
```

### 3. Run Evaluation
Execute from this directory:
```bash
promptfoo eval
```

### 4. View Results
Open the web viewer to see a detailed comparison:
```bash
promptfoo view
```

## 🧪 Test Scenarios

The `cases.yaml` covers:
- **BASIC_POSITIVE**: Clear time mentions.
- **TIME_PARSING**: Relative times, Russian/English idioms, multiple events.
- **DISAMBIGUATION**: Refusals, corrections, evening/morning inference.
- **EDGE**: Past events, bare numbers, complex phrasing.
- **SECURITY**: Prompt injection and jailbreak attempts.

## 📈 Optimization Goals

We aim for:
1. **Zero False Negatives**: All legitimate time mentions must be detected.
2. **Correct AM/PM Inference**: Especially for Russian bare-hour mentions (e.g., "в 8").
3. **Structured Stability**: The output must always be valid JSON matching our `MessageContext` requirements.
