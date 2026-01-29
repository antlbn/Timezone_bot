"""
Capture module.
Extracts time strings from messages using regex patterns from config.
"""
import re
from src.config import get_capture_patterns


def extract_times(text: str) -> list[str]:
    """
    Extract all time strings from a message.
    
    Args:
        text: Message text to scan
        
    Returns:
        List of matched time strings (e.g. ["14:00", "5 pm"])
    """
    patterns = get_capture_patterns()
    matches = []
    
    for pattern in patterns:
        # Use finditer to get full match, not just groups
        for m in re.finditer(pattern, text, re.IGNORECASE):
            matches.append(m.group(0))  # Full match, not groups
    
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    
    return unique
