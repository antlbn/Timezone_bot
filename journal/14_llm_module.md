# 14. LLM Module

- Hidden behind the `DetectionPort`.
- Two implementations: `GroqDetectionAdapter` (Primary) and `LiteLLMDetectionAdapter` (Fallback, Gemini).
- LLM returns JSON, strictly parsed by **Pydantic** into a `DetectionResult` domain object. No raw dictionaries.
