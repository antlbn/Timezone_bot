import pytest
from src.capture import extract_times
from src.transform import parse_time_string
from datetime import time

@pytest.mark.parametrize("text, expected_part", [
    # --- Group 1: Standard Regex (L1 Priority) ---
    ("Давай в 17:00", "17:00"),
    ("Meeting at 5 pm", "5 pm"),
    ("Call at 10:30am", "10:30am"),
    ("созвон в 14:15", "14:15"),
    
    # --- Group 2: Russian NLP (Standard) ---
    ("В 9 вечера удобно?", "9:00 pm"), # Now with :00
    ("Давай завтра утром в 8", "завтра am в 8:00"), 
    ("Встреча в полдень", "12:00"), 
    ("Ровно в полночь", "00:00"), 
    ("Давай в 4 ночи", "4:00 am"), 
    
    # --- Group 3: English NLP (Standard) ---
    ("Let's meet at midnight", "midnight"),
    ("See you at noon", "noon"),
    ("Schedule for next Monday at 10am", "10am"), 
    
    # --- Group 4: Relative Time (NLP) ---
    ("Буду через 2 часа", "через 2 часа"),
    ("I'll be there in 20 mins", "in 20 minutes"), 
    ("Напишу через 15 минут", "через 15 минут"),
    ("Start in 5 hours", "in 5 hours"),
    
    # --- Group 5: Colloquial / Complex (The "Top" Request) ---
    ("через 30 минут", "через 30 минут"),
    ("через 1,5 часа", "через 1,5 часа"), 
    ("в 3 часа дня", "в 3:00 часа pm"), # "в 3 часа" -> "в 3:00 часа"
    ("завтра вечером в 6", "завтра pm в 6:00"), 
    ("Tomorrow at 2 evening", "tomorrow at 2:00 pm"), # Rush typing
    ("at 2 evening", "at 2:00 pm"), # "evening" keyword + digit 2
])
def test_extract_times_heavy(text, expected_part):
    results = extract_times(text)
    assert results, f"Failed to detect time in: '{text}'"
    
    # Check if expected part is contained in one of the matches (case insensitive)
    found = False
    for res in results:
        # Check strict substring (expected in result)
        if expected_part.lower() in res.lower():
            found = True
            break
            
    if not found:
        print(f"DEBUG: Text='{text}' -> Results={results}")
        
    assert found, f"Expected '{expected_part}' in {results} for input '{text}'"

def test_negative_cases():
    negatives = [
        "Привет, как дела?",
        "Стоимость подписки 100 рублей",
        "Я купил 2 яблока",
        "Just a random phrase",
        "Wait a sec", # 'sec' removed from keywords
        "I am at home", # "at" is keyword, but NO DIGIT -> Ignore
        
        # --- Tricky False Positives candidates ---
        "This is not in my house", 
        "Man of the hour",         # Should be ignored (no digit)
        "Wait a minute",           # Should be ignored (no digit)
        "Not today",               # Should be ignored (no digit)
        "Good morning",            # Should be ignored (no digit)
    ]
    for text in negatives:
        # We expect these NOT to trigger a timezone conversion (empty list)
        # If they do, it's a false positive we need to handle.
        res = extract_times(text)
        assert res == [], f"False Positive detected! '{text}' parsed as {res}"

def test_parse_time_string_nlp():
    # 9 pm is reliable
    t = parse_time_string("9 pm")
    assert t.hour == 21, f"Expected 21, got {t.hour}"
    assert t.minute == 0

def test_parse_time_string_mixed():
    t = parse_time_string("в 15:30")
    assert t.hour == 15
    assert t.minute == 30
