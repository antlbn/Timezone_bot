"""
Capture module.
Extracts time strings from messages using Hybrid Pipeline:
L1: Strict Regex
L1.5: Keyword Filter
L2: NLP (dateparser)
"""
import re
import dateparser
from dateparser.search import search_dates
from src.config import get_capture_patterns, get_capture_keywords

def extract_times(text: str) -> list[str]:
    """
    Extract all time strings from a message.
    
    Args:
        text: Message text to scan
        
    Returns:
        List of matched time strings (e.g. ["14:00", "5 pm", "в 9 вечера"])
    """
    # L1: Strict Regex (Fastest)
    patterns = get_capture_patterns()
    matches = []
    
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            matches.append(m.group(0))
            
    if matches:
        return _deduplicate(matches)
        
    # L1.5: Keyword Filter (Fast)
    # Check if any trigger word exists in text
    keywords = get_capture_keywords()
    text_lower = text.lower()
    
    # Simple substring search is faster than regex for keywords
    has_keyword = any(kw.lower() in text_lower for kw in keywords)
    
    if not has_keyword:
        return []
        
    # L2: NLP Parser (Slow but smart)
    # We use search_dates to find dates inside text
    try:
        # languages=['ru', 'en'] explicitly to speed up
        results = search_dates(
            text, 
            languages=['ru', 'en'],
            settings={'PREFER_DATES_FROM': 'future'}
        )
        
        if results:
            # results is list of tuples: [('in 2 hours', datetime_obj), ...]
            # We return the original substring that was matched
            for time_str, _ in results:
                matches.append(time_str)
                
    except Exception:
        # Fallback if dateparser fails
        pass

    return _deduplicate(matches)

def _deduplicate(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for m in items:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique
