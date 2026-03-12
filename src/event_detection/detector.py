import json
from src.logger import get_logger
from src.event_detection.client import get_llm_client, get_llm_model
from src.event_detection.prompts import get_system_prompt
from src.config import get_bot_settings

logger = get_logger()

async def call_llm(messages: list[dict], expect_json: bool = True) -> str:
    """Wrapper to call the configured agnostic LLM API."""
    client = get_llm_client()
    model = get_llm_model()
    settings = get_bot_settings()
    temp = settings.get("event_detection", {}).get("temperature", 0.0)
    
    response_format = {"type": "json_object"} if expect_json else None
    
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temp,
        response_format=response_format
    )
    
    return response.choices[0].message.content

async def _parse_llm_response(raw_json: str) -> dict:
    """Safely parse LLM JSON and enforce defaults if schema breaks."""
    try:
        data = json.loads(raw_json)
        # Ensure minimum schema shape matching the new instruction
        reflections = data.get("reflections", {})
        return {
            "event": bool(data.get("event", False)),
            "time": list(data.get("time", [])),
            "city": list(data.get("city", [])),
            "reflections": {
                "event_logic": str(reflections.get("event_logic", "")),
                "time_logic": str(reflections.get("time_logic", "")),
                "geo_logic": str(reflections.get("geo_logic", ""))
            },
            # Compatibility fields for legacy orchestration
            "trigger": bool(data.get("event", False)),
            "times": list(data.get("time", [])),
            "event_location": data.get("city")[0] if data.get("city") and len(data.get("city")) > 0 else None,
            "confidence": 1.0 if data.get("event") else 0.5 # Force pass 2 if no event
        }
    except Exception as e:
        logger.error(f"Error parsing LLM response or invalid format: {e}. Raw: {raw_json}")
        return {
            "event": False, 
            "time": [], 
            "city": [], 
            "reflections": {}, 
            "trigger": False, 
            "times": [], 
            "event_location": None
        }

async def analyze_message_pass(
    current_msg: dict, 
    snapshot_context: str | None = None, 
    is_pass2: bool = False
) -> dict:
    """
    Constructs the prompt and calls the LLM.
    If snapshot_context is provided, prepends it to the user's message.
    """
    sys_prompt = get_system_prompt()
    
    # Message metadata helps LLM understand who is speaking (critical for group chats)
    author = current_msg.get("author_name", "Unknown")
    text = current_msg.get("text", "")
    
    user_content = ""
    if is_pass2 and snapshot_context:
        user_content += f"PREVIOUS CHAT CONTEXT:\n{snapshot_context}\n\n---\n\n"
        
    user_content += f"CURRENT MESSAGE:\n[{author}]: {text}"

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_content}
    ]
    
    raw_response = await call_llm(messages)
    return await _parse_llm_response(raw_response)

async def detect_event(current_msg: dict, snapshot: list[dict]) -> dict:
    """
    The orchestrator. Runs Pass 1. If low confidence, runs Pass 2 using snapshot.
    Returns the parsed JSON dictionary.
    """
    settings = get_bot_settings()
    min_confidence = settings.get("event_detection", {}).get("min_confidence_trigger", 0.75)
    
    # PASS 1: Current message only
    logger.debug(f"EventDetection Pass 1 for message: '{current_msg.get('text', '')}'")
    result = await analyze_message_pass(current_msg)
    
    if result["confidence"] >= min_confidence:
        return result
        
    # PASS 2: Add snapshot context if available
    if not snapshot:
        logger.debug("Pass 1 confidence low, but no snapshot available for Pass 2.")
        # Bias towards silence if uncertain
        result["trigger"] = False 
        return result
        
    from src.event_detection.history import format_snapshot_for_llm
    snapshot_str = format_snapshot_for_llm(snapshot)
    
    logger.info("Pass 1 confidence low. Executing Pass 2 with historical context.")
    result_p2 = await analyze_message_pass(
        current_msg, 
        snapshot_context=snapshot_str, 
        is_pass2=True
    )
    
    # If Pass 2 is still uncertain, we trust it.
    return result_p2
