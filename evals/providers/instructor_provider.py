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
        description="City or timezone name mentioned for THIS specific time. Use null if not specified.",
    )
    event_title: Optional[str] = Field(
        default=None,
        description="Optional short event label for this specific time point.",
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
    Promptfoo provider for structured extraction using Instructor.
    Compatible with Google Gemini (OpenAI bridge), Groq, and OpenRouter.
    """
    config = options.get("config", {})
    model_path = config.get("model", "")
    temperature = config.get("temperature", 0.1)

    # Resolve provider settings
    if model_path.startswith("google/"):
        api_key = os.environ.get("GOOGLE_API_KEY")
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        model = model_path.replace("google/", "")
    elif model_path.startswith("groq/"):
        api_key = os.environ.get("GROQ_API_KEY")
        base_url = "https://api.groq.com/openai/v1"
        model = model_path.replace("groq/", "")
    elif model_path.startswith("openrouter/"):
        api_key = os.environ.get("OPENROUTER_API_KEY")
        base_url = "https://openrouter.ai/api/v1"
        model = model_path.replace("openrouter/", "")
    else:
        return {"error": f"Unsupported model prefix in '{model_path}'. Use google/, groq/, or openrouter/."}

    if not api_key:
        return {"error": f"Missing API key for {model_path}"}

    client = instructor.from_openai(
        OpenAI(base_url=base_url, api_key=api_key),
        mode=instructor.Mode.JSON,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": context['prompt']}],
            response_model=TimezoneResponse,
            temperature=temperature,
        )
        return {"output": response.model_dump_json(indent=2)}
    except Exception as e:
        return {"error": f"Instructor call failed: {str(e)}"}
