import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from src.event_detection.prompts import get_system_prompt


def call_api(prompt, options, context):
    vars_ = context.get("vars", {})
    text = vars_.get("text", "")
    timestamp = vars_.get("timestamp", "")
    sys_prompt = get_system_prompt()

    rendered_prompt = (
        f"{sys_prompt}\n\nCURRENT TIME (UTC): {timestamp}\nCURRENT MESSAGE:\n{text}"
    )
    return {"output": rendered_prompt}
