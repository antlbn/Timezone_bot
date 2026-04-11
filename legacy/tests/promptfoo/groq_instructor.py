import json
import os
from typing import List, Optional

import instructor
from groq import Groq
from pydantic import BaseModel, Field


# Define the exact output schema expected by promptfoo assertions
class TimePoint(BaseModel):
    time: str = Field(description="Time in exact HH:MM format (24 hour clock).")
    city: Optional[str] = Field(
        default=None,
        description="City or timezone label for this time point, if explicitly present.",
    )
    event_title: Optional[str] = Field(
        default=None,
        description="Optional short event label for this specific time point.",
    )


class TimezoneResponse(BaseModel):
    event: bool = Field(
        description="True if the message proposes or coordinates an event with time."
    )
    points: List[TimePoint] = Field(
        description="List of extracted time points for the current message."
    )


def call_api(prompt, options, context):
    """
    Instructor-based Groq provider for promptfoo.
    This mirrors the current runtime contract: JSON-only, current message only,
    and `points[]` instead of legacy parallel `time[]`/`city[]` arrays.
    """
    # Ensure atomic API key reading
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY environment variable is not set"}

    # Initialize Instructor-patched Groq client using JSON mode instead of Tools
    client = instructor.from_groq(Groq(api_key=api_key), mode=instructor.Mode.JSON)

    # Options provided in promptfooconfig.yaml config block
    config = options.get("config", {})
    model = config.get("model", "llama-3.1-8b-instant")
    temperature = config.get("temperature", 0.1)

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_model=TimezoneResponse,
            temperature=temperature,
            max_retries=2,
        )
        result_dict = resp.model_dump()
        return {"output": json.dumps(result_dict, ensure_ascii=False)}

    except Exception as e:
        return {"error": f"Failed to call Groq with Instructor: {str(e)}"}
