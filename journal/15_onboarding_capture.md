# 15. Onboarding Flow

Split into two services (avoids God Object):
1. **`OnboardingPromptService`**: Called by the pipeline if the author lacks a timezone. Saves the message to `pending` and prompts the user to select a city.
2. **`OnboardingCompletionUseCase`**: Triggered by a button/command. Deletes the `pending` message, updates the DB, and "replays" the original message through the pipeline with the newly set timezone. Message age is controlled via `TimePort`.
