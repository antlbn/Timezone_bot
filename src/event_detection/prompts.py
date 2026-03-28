import json

# ─────────────────────────────────────────────────────────────────────────────
# JSON SCHEMA — what the LLM must return
# ─────────────────────────────────────────────────────────────────────────────
EVENT_DETECTION_SCHEMA = {
    "type": "object",
    "required": ["event", "points"],
    "additionalProperties": False,
    "properties": {
        "event": {"type": "boolean"},
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
SYSTEM_PROMPT = (
    """ВЫВОДИ ТОЛЬКО JSON. ОТВЕТ НАЧИНАЕТСЯ С { И ЗАКАНЧИВАЕТСЯ НА }.
БЕЗ ЛИШНЕГО ТЕКСТА И ПОЯСНЕНИЙ.

ЗАДАЧА:
Проанализируй CURRENT MESSAGE.
Цель: извлечь из сообщения конкретноео времени встречи/созвона/события, и ВАЖНО: извлекай время ТОЛЬКО когда оно указано однозначно.

ПРАВИЛА ИЗВЛЕЧЕНИЯ ВРЕМЕНИ:
1. 24-часовой формат строго, «8 вечера» = 20:00, «пол десятого» = 09:30 или 21:30 по контексту. 
2. Относительное время вычисляй от CURRENT TIME (UTC): «через час» (in 1 hr) при 11:21 → 12:21. 
3. СТРУКТУРА: используй массив 'points', где каждый объект содержит 'time', 'city' и 'event_type'.
4. event_type: короткое название события (например, "созвон", "дедлайн"). Если из контекста не ясно, используй общее "событие".
5. Игнорируй невозможные сочетания времени (напр. '13 ночи'). 
6. Когда event=false: points=[].

JSON SCHEMA:
"""
    + json.dumps(EVENT_DETECTION_SCHEMA, indent=2, ensure_ascii=False)
    + """

ПРИМЕРЫ:

Пример 1 — чёткое событие:
CURRENT MESSAGE:
Завтра в 8 вечера ок?
→ {"event":true,"points":[{"time":"20:00","city":null,"event_type":"встреча"}]}

Пример 2 — явный город:
CURRENT MESSAGE:
sync tomorrow at 9am EST, that's 2pm London
→ {"event":true,"points":[{"time":"14:00","city":"London","event_type":"sync"}]}

Пример 3 — нет уточнённого времени:
CURRENT MESSAGE:
ребят вы серьезно?
→ {"event":false,"points":[]}
"""
)

def get_system_prompt() -> str:
    return SYSTEM_PROMPT
