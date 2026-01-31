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
    
    # Fast check: words from config
    has_keyword = any(kw.lower() in text_lower for kw in keywords)
    
    if not has_keyword:
        return []
        
    # ANTI-SPAM RULE: Require a digit OR specific strong keywords (noon, midnight...)
    # This avoids false positives like "Man of the hour", "Wait a minute".
    # User preference: Better to miss "half an hour" than catch "spam".
    strong_keywords = {"noon", "midnight", "полдень", "полночь"}
    has_strong = any(k in text_lower for k in strong_keywords)
    has_digit = any(c.isdigit() for c in text)
    
    if not (has_strong or has_digit):
        return []
        
    # L2: NLP Parser (Slow but smart)
    # Preprocess text to help dateparser with Russian colloquialisms
    text_for_nlp = _preprocess_for_nlp(text)

    # We use search_dates to find dates inside text
    try:
        # languages=['ru', 'en'] explicitly to speed up
        results = search_dates(
            text_for_nlp, 
            languages=['ru', 'en'],
            settings={'PREFER_DATES_FROM': 'future'}
        )
        
        if results:
            # results is list of tuples: [('in 2 hours', datetime_obj), ...]
            # We return the original match from preprocessed text
            # Ideally verify if it matches original text logic, but acceptable for MVP
            for time_str, _ in results:
                # If the match was a result of substitution (e.g. "9 pm" from "9 вечера")
                # we return the substituted string effectively.
                # Transforming this back to original string is hard, so we return the understood string.
                # This string will be passed to parse_time_string later.
                matches.append(time_str)
                
    except Exception:
        pass

    return _deduplicate(matches)

def _preprocess_for_nlp(text: str) -> str:
    """
    Replace colloquial tokens with standard formats for better dateparser recognition.
    """
    t = text.lower()
    # Russian replacements
    t = re.sub(r'\b(вечер[ао][м]?)\b', 'pm', t) # вечера, вечером
    t = re.sub(r'\b(утр[ао][м]?)\b', 'am', t)   # утра, утром
    t = re.sub(r'\b(дн[яё])\b', 'pm', t)        # дня
    t = re.sub(r'\b(ноч[ьи][ю]?)\b', 'am', t)   # ночи, ночью
    t = re.sub(r'\bполдень\b', '12:00', t)
    t = re.sub(r'\bполночь\b', '00:00', t)
    
    # "в 8" -> "в 8:00" rule
    # Fixes "завтра в 8" being parsed as just "tomorrow"
    # Matches "в" or "at" followed by 1-2 digits, NOT followed by colon
    t = re.sub(r'\b(в|at)\s+(\d{1,2})\b(?!:)', r'\1 \2:00', t)
    
    # English colloquialisms (User Concept: "rush typing support")
    # "2 evening" -> "2 pm", "2:00 evening" -> "2:00 pm"
    t = re.sub(r'\b(\d{1,2}(?::\d{2})?)\s*evening\b', r'\1 pm', t)
    t = re.sub(r'\b(\d{1,2}(?::\d{2})?)\s*morning\b', r'\1 am', t)
    
    # English/Universal
    t = re.sub(r'\bmins\b', 'minutes', t)
    
    return t

def _deduplicate(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for m in items:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique
