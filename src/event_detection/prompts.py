import json

# ─────────────────────────────────────────────────────────────────────────────
# JSON SCHEMA — what the LLM must return (validated by _parse_llm_response)
# ─────────────────────────────────────────────────────────────────────────────
EVENT_DETECTION_SCHEMA = {
    "type": "object",
    "required": ["reflections", "event", "sender_id", "sender_name", "time", "city"],
    "additionalProperties": False,
    "properties": {
        "reflections": {
            "type": "object",
            "required": ["event_logic", "time_logic", "geo_logic"],
            "properties": {
                "event_logic": {"type": "string"},
                "time_logic":  {"type": "string"},
                "geo_logic":   {"type": "string"},
            },
        },
        "event":       {"type": "boolean"},
        "sender_id":   {"type": "string"},
        "sender_name": {"type": "string"},
        "time": {
            "type": "array",
            "items": {"type": "string"},
        },
        "city": {
            "type": "array",
            "items": {"type": ["string", "null"]},
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# CONVERT_TIME TOOL DEFINITION
# Passed to the LLM via the `tools` parameter so it can call it directly.
# ─────────────────────────────────────────────────────────────────────────────
CONVERT_TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "convert_time",
        "description": (
            "Convert event time(s) to local time for all chat participants. "
            "Call this whenever event=true and time[] is non-empty. "
            "Pass exactly the sender_id, sender_name, time[], and city[] "
            "from your JSON analysis."
        ),
        "parameters": {
            "type": "object",
            "required": ["sender_id", "sender_name", "time", "city"],
            "additionalProperties": False,
            "properties": {
                "sender_id": {
                    "type": "string",
                    "description": "Platform user ID of the message author (echo from SENDER block).",
                },
                "sender_name": {
                    "type": "string",
                    "description": "Display name of the message author (echo from SENDER block).",
                },
                "time": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Non-empty list of times extracted from the message (HH:MM 24h).",
                },
                "city": {
                    "type": "array",
                    "items": {"type": ["string", "null"]},
                    "description": (
                        "Parallel to 'time'. Each entry is the explicit city/timezone context "
                        "for time[i], or null to use the sender's stored timezone."
                    ),
                },
            },
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """ВЫВОДИ ТОЛЬКО JSON. ОТВЕТ НАЧИНАЕТСЯ С { И ЗАКАНЧИВАЕТСЯ НА }.

ЗАДАЧА:
Проанализируй CURRENT MESSAGE с учётом HISTORY и метаданных отправителя (SENDER / ANCHOR).
Цель: определить, содержит ли сообщение координацию события с временем, и извлечь времена.

АЛГОРИТМ ОТВЕТА:
А) event_logic — есть ли встреча, созвон, дедлайн или договорённость с временем?
Б) time_logic — переведи все упомянутые времена в 24-часовой формат (HH:MM).
В) geo_logic — есть ли явное упоминание города/часового пояса для каждого времени?
Г) Заполни JSON строго по схеме ниже, эхом вернув sender_id и sender_name из блока SENDER.

ПРАВИЛА ИЗВЛЕЧЕНИЯ ВРЕМЕНИ:
1. 24-часовой формат строго, «8 вечера» = 20:00, «пол десятого» = 09:30 или 21:30 по контексту.
2. Относительное время вычисляй от ANCHOR: «через час» при ANCHOR 12:21 → 13:21.
3. Если два времени указывают одно событие в разных зонах — выбери одно и запиши город.
4. Числа в нетемпоральном контексте (номера, этажи) — НЕ время.
5. Когда event=false: time=[], city=[].

JSON SCHEMA:
""" + json.dumps(EVENT_DETECTION_SCHEMA, indent=2, ensure_ascii=False) + """

ПРИМЕРЫ:

Пример 1 — чёткое событие:
SENDER: id=42  name=Антон
ANCHOR: 2026-03-13T15:00:00Z
HISTORY:
[Иван]: когда созвонимся?
CURRENT MESSAGE:
[Антон]: Завтра в 8 вечера ок?
→ {"reflections":{"event_logic":"предлагается созвон завтра вечером","time_logic":"8 вечера = 20:00","geo_logic":"город не указан"},"event":true,"sender_id":"42","sender_name":"Антон","time":["20:00"],"city":[null]}

Пример 2 — явный город:
SENDER: id=7  name=Jane
ANCHOR: 2026-03-13T18:00:00Z
HISTORY:
[Lead]: включи американских коллег
CURRENT MESSAGE:
[Jane]: sync tomorrow at 9am EST, that's 2pm London
→ {"reflections":{"event_logic":"синхронизация с США завтра","time_logic":"2pm London = 14:00, берём лондонское","geo_logic":"London"},"event":true,"sender_id":"7","sender_name":"Jane","time":["14:00"],"city":["London"]}

Пример 3 — нет события:
SENDER: id=99  name=Оля
ANCHOR: 2026-03-13T21:22:00Z
HISTORY:
CURRENT MESSAGE:
[Оля]: ребят вы серьезно? у нас есть чат для флуда
→ {"reflections":{"event_logic":"флуд, нет события","time_logic":"время не упоминается","geo_logic":"нет"},"event":false,"sender_id":"99","sender_name":"Оля","time":[],"city":[]}
"""


def get_system_prompt() -> str:
    return SYSTEM_PROMPT


def get_tools() -> list[dict]:
    """Return the list of function tools to register with the LLM call."""
    return [CONVERT_TIME_TOOL]
