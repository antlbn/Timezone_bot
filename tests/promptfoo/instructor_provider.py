import json
import os
from typing import List, Optional

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field


class TimePoint(BaseModel):
    time: str = Field(description="Time in exact HH:MM format (24 hour clock).")
    city: Optional[str] = Field(
        default=None,
        description="City or timezone name mentioned for THIS specific time. Use null if not specified."
    )
    event_title: Optional[str] = Field(
        default=None,
        description="Optional short event label for this specific time point."
    )


class TimezoneResponse(BaseModel):
    event: bool = Field(
        description="True if the message discusses a specific upcoming meeting, call, or event coordination. False if it's just chatter or past events."
    )
    points: List[TimePoint] = Field(
        description="List of extracted time points. If one event is mentioned in multiple zones, PICK ONLY ONE (the most specific one)."
    )


def call_api(prompt, options, context):
    """
    Universal OpenRouter/Groq provider function for Promptfoo using Instructor.
    Config options:
      - model: e.g. "openrouter/nvidia/nemotron-3-super-120b-a12b:free" or "groq/llama-3.1-8b-instant"
      - temperature: float
    This provider follows the current runtime-style schema: `event` + `points[]`.
    """
    config = options.get("config", {})
    full_model_name = config.get("model", "")
    temperature = config.get("temperature", 0.1)

    # Determine provider and API key
    if full_model_name.startswith("openrouter/"):
        api_key = os.environ.get("OPENROUTER_API_KEY")
        base_url = "https://openrouter.ai/api/v1"
        model = full_model_name.replace("openrouter/", "")
    elif full_model_name.startswith("groq/"):
        api_key = os.environ.get("GROQ_API_KEY")
        base_url = "https://api.groq.com/openai/v1"
        model = full_model_name.replace("groq/", "")
    elif full_model_name.startswith("google/"):
        api_key = os.environ.get("GOOGLE_API_KEY")
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        model = full_model_name.replace("google/", "")
    else:
        return {"error": "Model must start with 'openrouter/', 'groq/', or 'google/'"}

    if not api_key:
        return {
            "error": f"API key for {full_model_name} is not set in environment variables."
        }

    # Initialize Instructor-patched OpenAI client
    # We use Mode.JSON to ensure maximum compatibility across different open-source models
    client = instructor.from_openai(
        OpenAI(
            base_url=base_url,
            api_key=api_key,
        ),
        mode=instructor.Mode.JSON,
    )

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
        return {"error": f"Failed to call {model} via Instructor: {str(e)}"}
