"""
push_prompts.py — Push the production system prompt to LangSmith Prompt Hub.

Usage:
    uv run python tests/langsmith/push_prompts.py

After running:
  → Prompt visible in LangSmith UI → Prompts section
  → URL: https://eu.smith.langchain.com/prompts/timezone-bot-system-prompt

Pulling in production (optional future use):
    from langsmith import Client
    prompt = Client().pull_prompt("timezone-bot-system-prompt")
"""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path (needed when running script directly)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# ── Import production prompt ────────────────────────────────────────────────
from src.event_detection.prompts import get_system_prompt

PROMPT_NAME = "timezone-bot-system-prompt"


def main():
    client = Client()

    system_text = get_system_prompt()

    # Wrap in a ChatPromptTemplate — LangSmith stores prompts in this format
    # Using a simple {user_content} variable as the user turn placeholder
    template = ChatPromptTemplate.from_messages([
        ("system", system_text),
        ("human", "{user_content}"),   # filled at runtime by detector.py
    ])

    try:
        url = client.push_prompt(
            PROMPT_NAME,
            object=template,
            description=(
                "Event detection system prompt for the Timezone Bot. "
                "Instructs a LangChain agent to detect meeting/deadline times in chat messages "
                "and call publish_event or update_previous_event tools."
            ),
        )
        print(f"✅ Prompt pushed: {PROMPT_NAME}")
        print(f"   URL: {url}")
    except Exception as e:
        if "Nothing to commit" in str(e) or "409" in str(e):
            print(f"ℹ️  Prompt unchanged — no new version created (already up to date)")
            print(f"   View at: https://eu.smith.langchain.com/prompts/{PROMPT_NAME}")
        else:
            raise

    print(f"\nTo pull in code:")
    print(f"   from langsmith import Client")
    print(f"   prompt = Client().pull_prompt('{PROMPT_NAME}')")



if __name__ == "__main__":
    main()
