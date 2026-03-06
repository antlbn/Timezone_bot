import re
from src.config import get_prefilter_settings
from src.logger import get_logger

logger = get_logger()

def should_call_llm(text: str) -> bool:
    """
    Decides whether to call the LLM based on the prefilter settings.
    If prefilter is disabled, always returns True.
    """
    settings = get_prefilter_settings()
    if not settings.get("enabled", False):
        return True
        
    text_lower = text.lower()
    
    # 1. Check strict time regex
    strict_patterns = settings.get("strict_patterns", [])
    for p in strict_patterns:
        if re.search(p, text, re.IGNORECASE):
            logger.debug(f"Prefilter: strict match found for pattern '{p}'")
            return True
            
    # 2. Check keywords + numeric candidates
    keywords = settings.get("keywords", [])
    has_keyword = any(k.lower() in text_lower for k in keywords)
    
    if has_keyword:
        numeric_pattern = settings.get("numeric_candidate_pattern", r"\b([0-1]?[0-9]|2[0-3])\b")
        if re.search(numeric_pattern, text):
            logger.debug("Prefilter: keyword + numeric candidate match found")
            return True
            
    logger.debug("Prefilter: no match, LLM call skipped")
    return False
