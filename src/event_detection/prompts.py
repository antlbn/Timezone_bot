import json

# ─────────────────────────────────────────────────────────────────────────────
# JSON SCHEMA — what the LLM must return (validated by _parse_llm_response)
# ─────────────────────────────────────────────────────────────────────────────
EVENT_DETECTION_SCHEMA = {
    "type": "object",
    "required": ["reflections", "event", "sender_id", "sender_name", "points"],
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
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["time", "city", "event_type"],
                "properties": {
                    "time": {"type": "string"},
                    "city": {"type": ["string", "null"]},
                    "event_type": {"type": "string"},
                },
            },
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """ВЫВОДИ ТОЛЬКО JSON. ОТВЕТ НАЧИНАЕТСЯ С { И ЗАКАНЧИВАЕТСЯ НА }.
БЕЗ ЛИШНЕГО ТЕКСТА И ПОЯСНЕНИЙ.

ЗАДАЧА:
Проанализируй CURRENT MESSAGE с учётом HISTORY и метаданных отправителя (SENDER / ANCHOR).
Цель: определить, содержит ли сообщение обсуждение, предложение или уточнение времени встречи, созвона или дедлайна (даже если это отказ от времени), и извлечь их.

АЛГОРИТМ ОТВЕТА:
А) event_logic — есть ли встреча, дедлайн, обсуждение или уточнение (в т.ч. отказ) конкретного времени?
Б) time_logic — переведи все упомянутые времена в 24-часовой формат (HH:MM).
В) geo_logic — есть ли явное упоминание города/часового пояса для каждого времени?
Г) Заполни JSON строго по схеме ниже, эхом вернув sender_id и sender_name из блока SENDER.

ПРАВИЛА ИЗВЛЕЧЕНИЯ ВРЕМЕНИ:
1. 24-часовой формат строго, «8 вечера» = 20:00, «пол десятого» = 09:30 или 21:30 по контексту.
2. Относительное время вычисляй от ANCHOR: «через час» при ANCHOR 12:21 → 13:21.
3. ДЕДУПЛИКАЦИЯ: Если одно событие указано в нескольких зонах (например, "9:00 EST / 14:00 London") — выбери ОДНО наиболее точное время и запиши город. Не выводи дубликаты одного события.
4. СТРУКТУРА: используй массив 'points', где каждый объект содержит 'time', 'city' и 'event_type'.
5. event_type: короткое название события (например, "созвон", "дедлайн", "запуск деплоя"). Если из контекста не ясно, используй общее "встреча" или "событие".
6. Числа в нетемпоральном контексте (номера, этажи) — НЕ время.
7. Когда event=false: points=[].

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
→ {"reflections":{"event_logic":"предлагается созвон завтра вечером","time_logic":"8 вечера = 20:00","geo_logic":"город не указан"},"event":true,"sender_id":"42","sender_name":"Антон","points":[{"time":"20:00","city":null,"event_type":"созвон"}]}

Пример 2 — явный город:
SENDER: id=7  name=Jane
ANCHOR: 2026-03-13T18:00:00Z
HISTORY:
[Lead]: включи американских коллег
CURRENT MESSAGE:
[Jane]: sync tomorrow at 9am EST, that's 2pm London
→ {"reflections":{"event_logic":"синхронизация с США завтра","time_logic":"2pm London = 14:00, берём лондонское","geo_logic":"London"},"event":true,"sender_id":"7","sender_name":"Jane","points":[{"time":"14:00","city":"London","event_type":"sync"}]}

Пример 3 — нет события:
SENDER: id=99  name=Оля
ANCHOR: 2026-03-13T21:22:00Z
HISTORY:
CURRENT MESSAGE:
[Оля]: ребят вы серьезно? у нас есть чат для флуда
→ {"reflections":{"event_logic":"флуд, нет события","time_logic":"время не упоминается","geo_logic":"нет"},"event":false,"sender_id":"99","sender_name":"Оля","points":[]}
"""


def get_system_prompt() -> str:
    return SYSTEM_PROMPT


def get_tools() -> list[dict]:
    """Return the list of function tools to register with the LLM call."""
    return []
