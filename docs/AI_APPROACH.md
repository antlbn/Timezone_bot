# AI Usage Approach

As requested in the assignment brief, here is a short overview of how AI tools were used during the development of this project.

## 1. Tools Used

*   **Claude/Cursor:** Used as the primary pair-programming assistant for writing code, refactoring, and generating boilerplate.
*   **Promptfoo** Used for systematically evaluating and tuning the LLM prompt (Event Detection) against a test suite of edge cases.
*   **DeepMind/Gemini (Current session):** Used for performing the final architectural audit, gap analysis against the assignment brief, and drafting handover documentation.

## 2. Methodology: AI as an Implementer, Human as an Architect

The development followed a "Spec-Driven Development" approach:
1.  **Human-defined specifications:** The canonical product rules, state machines, and architectural decisions (like the UTC-pivot, 4-layer memory, and SQLite schema) were conceptualized and documented by a human in the `journal/*.md` specs first.
2.  **AI-assisted implementation:** Cursor/Claude were instructed to implement the Python code strictly according to the specs. 
3.  **Human review and correction:** AI-generated code was reviewed for logical gaps, edge cases the AI missed (like handling Discord vs. Telegram lifecycle events), and performance considerations (adding LRU caching when DB reads became a bottleneck).

## 3. Where AI Excelled vs. Required Guidance

*   **Excisions & Refactoring:** AI was extremely fast at structural refactoring (e.g., extracting the `aiogram` middleware or decoupling the SQLite storage module).
*   **Test Generation:** AI wrote the bulk of the 176 `pytest` cases, specifically the boilerplate for mocking SQLite and the LLM client.
*   **State Management (Required Guidance):** The AI struggled with complex async state transitions, particularly around the "zero-friction onboarding" (deferring a user's first message until they complete onboarding). The concurrency locks and message aging logic required manual architectural design and explicit prompting to get right.

## 4. The Core Feature: LLM for Event Detection

The most significant AI component of this project isn't how the code was written, but the core feature itself: using an LLM (`gemini-2.0-flash-lite` / `llama-3.1-8b-instant`) strictly as an intelligence layer to replace brittle regex parsers for time detection. 

By enforcing a strict JSON output schema and evaluating it via `promptfoo`, the LLM turned a traditionally difficult NLP problem (extracting intent and relative times from natural chat) into a reliable API endpoint.
