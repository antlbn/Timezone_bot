import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from src.event_detection.prompts import get_system_prompt


def call_api(context):
    author = context["vars"].get("author", "Unknown")
    text = context["vars"].get("text", "")
    history = context["vars"].get("history", "No previous chat context.")
    sys_prompt = get_system_prompt()

    # We replace the placeholders in the prompt manually or rely on promptfoo.
    # Actually, promptfoo handles the {{history}}, {{author}}, {{text}} placeholders
    # if it's reading the file directly. But we are in a provider script.
    # Let's just return the messages and let promptfoo handle the rest,
    # OR we can format it here if promptfoo isn't doing it automatically for scripts.

    # Wait, if promptfoo uses this script, it might not apply the template itself.
    # Let's check how promptfooconfig.yaml is set up.

    return [
        {"role": "system", "content": sys_prompt},
        {
            "role": "user",
            "content": f"PREVIOUS CHAT CONTEXT:\n{history}\n\nCURRENT MESSAGE:\n[{author}]: {text}",
        },
    ]
