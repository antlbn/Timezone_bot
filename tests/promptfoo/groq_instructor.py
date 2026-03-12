import json
import os
import instructor
from groq import Groq
from pydantic import BaseModel, Field
from typing import List, Optional

# Define the exact output schema expected by promptfoo assertions
class Reflections(BaseModel):
    event_logic: str = Field(description="Reasoning for whether an event is present or not")
    time_logic: str = Field(description="Reasoning for the extracted time, if any")
    geo_logic: str = Field(description="Reasoning for the extracted city/timezone, if any")

class TimezoneResponse(BaseModel):
    reflections: Reflections
    event: bool
    time: List[str]
    city: List[Optional[str]]

def call_api(prompt, options, context):
    """
    Custom provider function for Promptfoo.
    See: https://promptfoo.dev/docs/providers/python/
    """
    # Ensure atomic API key reading
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY environment variable is not set"}

    # Initialize Instructor-patched Groq client using JSON mode instead of Tools
    client = instructor.from_groq(
        Groq(api_key=api_key),
        mode=instructor.Mode.JSON
    )

    # Options provided in promptfooconfig.yaml config block
    config = options.get("config", {})
    model = config.get("model", "llama-3.1-8b-instant")
    temperature = config.get("temperature", 0.1)

    try:
        # Instructor handles the strict JSON schema validation, retries, and clean extraction
        # We pass the full promptfoo prompt containing both system rules and user message
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
        
        # Convert Pydantic model back to a dictionary and then return as string
        # to ensure it behaves exactly like a raw API response holding JSON
        result_dict = resp.model_dump()
        return {
            "output": json.dumps(result_dict, ensure_ascii=False)
        }

    except Exception as e:
        return {
            "error": f"Failed to call Groq with Instructor: {str(e)}"
        }
