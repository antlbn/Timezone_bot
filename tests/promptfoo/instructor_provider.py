import json
import os

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Optional

# Define the exact output schema expected by promptfoo assertions
class Reflections(BaseModel):
    event_logic: str = Field(description="Step by step reasoning to determine if this message proposes or modifies an event/meeting.")
    time_logic: str = Field(description="Step by step calculation of the event time in 24h HH:MM format. If relative (e.g. 'in an hour'), explicitly add it to the ANCHOR time.")
    geo_logic: str = Field(description="Reasoning for the extracted city/timezone, if any.")

class TimePoint(BaseModel):
    time: str = Field(description="Time in exact HH:MM format (24 hour clock).")
    city: Optional[str] = Field(description="City or timezone name mentioned for THIS specific time. Use null if not specified.")

class TimezoneResponse(BaseModel):
    reflections: Reflections
    event: bool = Field(description="True if the message discusses a specific upcoming meeting, call, or event coordination. False if it's just chatter or past events.")
    points: List[TimePoint] = Field(description="List of extracted time points. If one event is mentioned in multiple zones, PICK ONLY ONE (the most specific one).")
    sender_id: str = Field(description="The exact sender_id given in the prompt's SENDER block.")
    sender_name: str = Field(description="The exact sender_name given in the prompt's SENDER block.")

def call_api(prompt, options, context):
    
        
    """
    Universal OpenRouter/Groq provider function for Promptfoo using Instructor.
    Config options:
      - model: e.g. "openrouter/nvidia/nemotron-3-super-120b-a12b:free" or "groq/llama-3.1-8b-instant"
      - temperature: float
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
        return {"error": f"API key for {full_model_name} is not set in environment variables."}

    # Initialize Instructor-patched OpenAI client
    # We use Mode.JSON to ensure maximum compatibility across different open-source models
    client = instructor.from_openai(
        OpenAI(
            base_url=base_url,
            api_key=api_key,
        ),
        mode=instructor.Mode.JSON
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_model=TimezoneResponse,
            temperature=temperature,
            max_retries=2
        )
        
        result_dict = resp.model_dump()
        return {
            "output": json.dumps(result_dict, ensure_ascii=False)
        }

    except Exception as e:
        return {
            "error": f"Failed to call {model} via Instructor: {str(e)}"
        }
