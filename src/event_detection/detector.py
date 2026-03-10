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
        # Ensure minimum schema shape
        return {
            "trigger": bool(data.get("trigger", False)),
            "polarity": str(data.get("polarity", "negative")),
            "confidence": float(data.get("confidence", 0.0)),
            "reason": str(data.get("reason", "")),
            "times": list(data.get("times", [])),
            "event_location": data.get("event_location") # string or None
        }
    except json.JSONDecodeError:
        logger.error(f"LLM returned invalid JSON: {raw_json}")
        return {"trigger": False, "confidence": 0.0, "times": [], "event_location": None}

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
    
    # If Pass 2 is still uncertain, bias towards silence.
    if result_p2["confidence"] < min_confidence:
        result_p2["trigger"] = False
        
    return result_p2
