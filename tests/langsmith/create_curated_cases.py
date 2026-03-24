"""
create_curated_cases.py — Create hand-crafted test examples in LangSmith.

These are NOT migrated from cases.yaml — they are purpose-built to test
the LangChain agent's tool-calling behavior specifically.

Ground truth per example includes:
  - event: true/false
  - tool: "publish_event" | "update_previous_event" | null
  - time: expected HH:MM string (or null)

Usage:
    uv run python tests/langsmith/create_curated_cases.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client  # noqa: E402

DATASET_NAME = "timezone-bot-tool-calls"

# ── Curated examples ───────────────────────────────────────────────────────
# Format:
#   inputs  = what the agent receives
#   outputs = ground truth we check in the evaluator
#
# tool values:
#   "publish_event"         — first mention of this event in chat
#   "update_previous_event" — corrects a time the bot already published
#   null                    — no event detected, no tool should be called

EXAMPLES = [

    # -- UPDATE: длинный спор (на русском, но event_type на английском)
    {
        "description": "[TOOL=update] Arguing around event (Complex Negotiation)",
        "inputs": {
            "text": "нет я настаиваю на том что нам стоит собраться в 10",
            "history": [
                {"type": "human", "content": "[2026-03-24T09:58:00Z] [Author: Jack]: давайте общий зум по scope of work завтра в 9 утра по Берлику"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"reflections": {"event_logic": "mock", "time_logic": "mock", "geo_logic": "mock", "tool_logic": "mock"}, "points": [{"time": "09:00", "city": "Berlin", "event_type": "zoom"}]}, "id": "tc1"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1. Summary: zoom → 09:00 (Berlin)", "tool_call_id": "tc1"},
                
                {"type": "human", "content": "[2026-03-24T09:59:00Z] [Author: Макс]: у меня будет глубокая ночь - я точно нужен?"},
                
                {"type": "human", "content": "[2026-03-24T10:02:00Z] [Author: Jess]: я посмотрела - можем в 11 если, что скажете?"},
                {"type": "ai", "tool_calls": [{"name": "update_previous_event", "args": {"reflections": {"event_logic": "mock", "time_logic": "mock", "geo_logic": "mock", "tool_logic": "mock"}, "event_ref": 1, "points": [{"time": "09:00", "city": "Berlin", "event_type": "zoom"}, {"time": "11:00", "city": "Berlin", "event_type": "sync"}], "comment": "UPDATE due to coordination"}, "id": "tc2"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event updated. event_ref: 1. Summary: zoom → 09:00 (Berlin), sync → 11:00. Comment: UPDATE due to coordination", "tool_call_id": "tc2"},
                
                {"type": "human", "content": "[2026-03-24T10:02:00Z] [Author: Jack]: в 11 тоже так себе у меня другой колл - давайте тогда в 12 - хотя-бы"},
                {"type": "ai", "tool_calls": [{"name": "update_previous_event", "args": {"reflections": {"event_logic": "mock", "time_logic": "mock", "geo_logic": "mock", "tool_logic": "mock"}, "event_ref": 1, "points": [{"time": "09:00", "city": "Berlin", "event_type": "zoom"}, {"time": "11:00", "city": "Berlin", "event_type": "sync"}, {"time": "12:00", "city": "Berlin", "event_type": "call"}], "comment": "UPDATE due to negotiation"}, "id": "tc3"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event updated. event_ref: 1. Summary: zoom → 09:00 (Berlin), sync → 11:00, call → 12:00. Comment: UPDATE due to negotiation", "tool_call_id": "tc3"}
            ],
            "sender_id": "hr2",
            "sender_name": "Jane",
            "timestamp": "2026-03-24T10:15:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "event_ref": 1,
            "points": [
                {"time": "10:00", "city": "Berlin", "event_type": "zoom [UPDATED]"} 
            ],
            "comment": "UPDATE due to coordination"
        },
    },

    # ── UPDATE: Add ISS passing to star-fall event ─────────────────────────
    {
        "description": "[TOOL=update] Add ISS passing to star-fall event",
        "inputs": {
            "text": "and approximately at 3 it,s possible to watch ISS pasing",
            "history": [
                {"type": "human", "content": "[2026-03-23T20:10:00Z] [Author: Anton]: in our rigion it will be star-fall from 10 to 6"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"reflections": {"event_logic": "mock", "time_logic": "mock", "geo_logic": "mock", "tool_logic": "mock"}, "points": [{"time": "22:00", "city": None, "event_type": "star-fall start"}, {"time": "06:00", "city": None, "event_type": "star-fall end"}]}, "id": "tc_starfall"}], "message_id": "m_starfall"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1071. Summary: star-fall start → 22:00, star-fall end → 06:00", "tool_call_id": "tc_starfall"}
            ],
            "sender_name": "Anton",
            "timestamp": "2026-03-23T20:12:26Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "event_ref": 1071,
            "points": [
                {"time": "22:00", "city": None, "event_type": "star-fall start"},
                {"time": "06:00", "city": None, "event_type": "star-fall end"},
                {"time": "03:00", "city": None, "event_type": "ISS passing"}
            ],
            "comment": "added ISS pass at 03:00"
        },
    },

    # ── PUBLISH: deadline with slang ───────────────────────────────────────
    {
        "description": "[TOOL=publish] Deadline with slang time",
        "inputs": {
            "text": "gotta ship the press release by 8 tonight ngl",
            "history": [
                {"type": "human", "content": "[2026-03-20T15:15:00Z] [Author: Jane]: any updates on the release?"},
                {"type": "human", "content": "[2026-03-20T15:20:00Z] [Author: Anton]: still waiting on sign-off"}
            ],
            "sender_id": "u2",
            "sender_name": "Anton",
            "timestamp": "2026-03-20T15:30:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "20:00", "city": None, "event_type": "deadline"}
            ],
            "comment": ""
        },
    },

    # ── UPDATE: коррекция времени (user2 corrects what bot already posted) ─
    {
        "description": "[TOOL=update] User corrects previously proposed time",
        "inputs": {
            "text": "нет давай лучше в 11, у меня в 10 другой звонок",
            "history": [
                {"type": "human", "content": "[2026-03-20T09:00:00Z] [Author: Иван]: созвон в 10 утра?"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"reflections": {"event_logic": "mock", "time_logic": "mock", "geo_logic": "mock", "tool_logic": "mock"}, "points": [{"time": "10:00", "city": None, "event_type": "созвон"}]}, "id": "tc1"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1. Summary: созвон → 10:00", "tool_call_id": "tc1"}
            ],
            "sender_id": "u2",
            "sender_name": "Петя",
            "timestamp": "2026-03-20T09:10:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "event_ref": 1,
            "points": [
                {"time": "11:00", "city": None, "event_type": "созвон"}
            ],
            "comment": "UPDATE due to coordination"
        },
    },

    # ── UPDATE: согласование после торга ──────────────────────────────────
    {
        "description": "[TOOL=update] Negotiation resolves to new time",
        "inputs": {
            "text": "ок, тогда в полвторого договорились",
            "history": [
                {"type": "human", "content": "[2026-03-20T10:00:00Z] [Author: Маша]: встреча в 14:00?"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"reflections": {"event_logic": "mock", "time_logic": "mock", "geo_logic": "mock", "tool_logic": "mock"}, "points": [{"time": "14:00", "city": None, "event_type": "встреча"}]}, "id": "tc1"}], "message_id": "m2"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1. Summary: встреча → 14:00", "tool_call_id": "tc1"},
                {"type": "human", "content": "[2026-03-20T10:05:00Z] [Author: Саша]: я не успею к 14, можно в 13:30?"}
            ],
            "sender_id": "u3",
            "sender_name": "Маша",
            "timestamp": "2026-03-20T10:20:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "event_ref": 1,
            "points": [
                {"time": "13:30", "city": None, "event_type": "встреча"}
            ],
            "comment": "UPDATE due to coordination"
        },
    },

    # ── NO EVENT: sarcastic/metaphorical time ──────────────────────────────
    {
        "description": "[TOOL=null] Sarcastic 'midnight' in history context",
        "inputs": {
            "text": "да-да, договорились — ровно в полночь, как в сказке 🙄",
            "history": [
                {"type": "human", "content": "[2026-03-24T11:30:00Z] [Author: Толя]: когда наконец встретимся по этому вопросу?"},
                {"type": "human", "content": "[2026-03-24T11:40:00Z] [Author: Рома]: ну ты сам всегда занят"},
                {"type": "human", "content": "[2026-03-24T11:50:00Z] [Author: Толя]: может в следующем году?"},
            ],
            "sender_id": "u_roma",
            "sender_name": "Рома",
            "timestamp": "2026-03-24T12:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
    },

    # ── PUBLISH: Availability window (multiple times) ──────────────────────
    {
        "description": "[TOOL=publish] Availability window — multiple times in one message",
        "inputs": {
            "text": "I am free between 14:00 and 17:30 tomorrow",
            "history": [
                {"type": "human", "content": "[2026-03-13T09:48:00Z] [Author: Recruiter]: Hi Elena, when can we talk?"},
                {"type": "human", "content": "[2026-03-13T09:53:00Z] [Author: Elena]: Hi!"},
            ],
            "sender_id": "304",
            "sender_name": "Elena",
            "timestamp": "2026-03-13T10:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "14:00", "city": None, "event_type": "availability"},
                {"time": "17:30", "city": None, "event_type": "availability"}
            ],
            "comment": ""
        },
    },

    # ── PUBLISH: explicit city / timezone ─────────────────────────────────
    {
        "description": "[TOOL=publish] Explicit city — take London time",
        "inputs": {
            "text": "sync tomorrow at 9am EST, that's 2pm London",
            "history": [
                {"type": "human", "content": "[2026-03-20T17:55:00Z] [Author: Lead]: include US colleagues please"}
            ],
            "sender_id": "u7",
            "sender_name": "Jane",
            "timestamp": "2026-03-20T18:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "14:00", "city": "London", "event_type": "sync"}
            ],
            "comment": ""
        },
    },

    # ── PUBLISH: Knowledge worker sync with history (flood + short pings + distracing time point in history) ──
    {
        "description": "[TOOL=publish] Knowledge worker sync (English, Slang, History)",
        "inputs": {
            "text": "Actually, let's hop on a quick sync for the Board Meeting at 5pm today.",
            "history": [
                {"type": "human", "content": "[2026-03-22T09:15:00Z] [Author: Alex]: That new RAG approach is absolute fire, we should double down on it ASAP."},
                {"type": "human", "content": "[2026-03-22T09:20:00Z] [Author: Jordan]: Hard agree, but let's circle back to the latency benchmarks first. Any word on that?"},
                {"type": "human", "content": "[2026-03-22T09:30:00Z] [Author: Alex]: Not yet, will loop back after I finish this PR review. COB today at 11 for sure."},
                {"type": "human", "content": "[2026-03-22T13:30:00Z] [Author: Taylor]: ping"},
                {"type": "human", "content": "[2026-03-22T13:32:00Z] [Author: Jordan]: ?"},
                {"type": "human", "content": "[2026-03-22T13:35:00Z] [Author: Taylor]: check slack pls"}
            ],
            "sender_id": "u8",
            "sender_name": "Taylor",
            "timestamp": "2026-03-22T14:40:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "17:00", "city": None, "event_type": "Board Meeting"}
            ],
            "comment": ""
        },
    },
    # ── EDGE: Number trap — 'встречаемся в 9' (building number) ─────────
    {
        "description": "[TOOL=null] Number trap — '9ка' (building) is not a time",
        "inputs": {
            "text": "встречаемся в девятом",
            "history": [
                {"type": "human", "content": "[2026-03-13T16:30:00Z] [Author: Гоша]: в каком здании встречаемся?"},
                {"type": "human", "content": "[2026-03-13T16:36:00Z] [Author: Степан]: едем на объект сегодня вечером"}
            ],
            "sender_id": "802",
            "sender_name": "Степан",
            "timestamp": "2026-03-13T16:40:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
    },
    # ── [MULTILANG] Spanish: '9 y media' correction ─────────────────────────
    {
        "description": "[MULTILANG] Spanish — '9 y media' correction, not '10:00'",
        "inputs": {
            "text": "mañana a las 9 y media, no a las 10 como dije antes",
            "history": [
                {"type": "human", "content": "[2026-03-13T16:47:00Z] [Author: Sofia]: ¿a qué hora mañana?"},
                {"type": "human", "content": "[2026-03-13T16:55:00Z] [Author: Carlos]: hablé con el cliente, hay cambios"}
            ],
            "sender_id": "806",
            "sender_name": "Carlos",
            "timestamp": "2026-03-13T17:02:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "09:30", "city": None, "event_type": "reunión"}
            ],
            "comment": ""
        },
    },
    # ── PUBLISH: Stress test (3 events + messy history + typos) ───────────
    {
        "description": "[TOOL=publish] Stress test — 3 events, massive history with typos",
        "inputs": {
            "text": "Man sry for writing so late im just buried in work and my brain is fried anyway about the loogistics call lets do thursdsy at 10:30 instead of half past nine as suggested coz i wont make it from the airport and also we really need to talk about the investor deck on Friday at 1 PM thats super critical and also remind me pls what about the code deadline on Monday by 5 PM are we on track? i am literally falling asleep here...",
            "history": [
                {"type": "human", "content": "[2026-03-13T21:15:00Z] [Author: Dima]: Hey colleagues, I was looking at our yesterday's sync from 9:00 AM and realized we have a massive workload ahead. Especially with the Munich logistics project we discussed last Friday at 4 PM. We should try to discuss everything this Wednesday around 2 PM if everyone is free."},
                {"type": "human", "content": "[2026-03-13T21:30:00Z] [Author: Elena]: Agree, Dima. That project takes a lot of time. I remember we had a session at 11 AM about it. I can't do Wednesday at 2 because of a legal call at 2:30. How about Thursday morning, say half past nine, so we can cover everything?"},
            ],
            "sender_id": "601",
            "sender_name": "Anton",
            "timestamp": "2026-03-13T22:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "10:30", "city": None, "event_type": "logistics call"},
                {"time": "13:00", "city": None, "event_type": "investor deck"},
                {"time": "17:00", "city": None, "event_type": "code deadline"}
            ],
            "comment": ""
        },
    },
    # ── PUBLISH: Slang + typos (Russian) ──────────────────────────────────
    {
        "description": "[TOOL=publish] Slang + typos — 'митос в 1500'",
        "inputs": {
            "text": "гы народ митос завтр в 1500 не проспите лан?",
            "history": [
                {"type": "human", "content": "[2026-03-13T13:02:00Z] [Author: Серый]: пашок ты живой?"},
                {"type": "human", "content": "[2026-03-13T13:09:00Z] [Author: Дэн]: задеплоили наконец-то ффух"},
            ],
            "sender_id": "701",
            "sender_name": "Пашок",
            "timestamp": "2026-03-13T13:14:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "15:00", "city": None, "event_type": "митинг"}
            ],
            "comment": ""
        },
    },
    # ── PUBLISH: Relative time (Russian) ──────────────────────────────────
    {
        "description": "[TOOL=publish] Relative time — 'через час'",
        "inputs": {
            "text": "через час будет созвон",
            "history": [
                {"type": "human", "content": "[2026-03-13T12:16:00Z] [Author: Admin]: Всем приготовиться."},
            ],
            "sender_id": "303",
            "sender_name": "Jane",
            "timestamp": "2026-03-13T12:21:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "13:21", "city": None, "event_type": "созвон"}
            ],
            "comment": ""
        },
    },
    # ── NO EVENT: Post-factum complaint ──────────────────────────────────
    {
        "description": "[TOOL=null] Post-factum complaint disguised as coordination",
        "inputs": {
            "text": "мы же договорились в 17:30, я прождал полчаса",
            "history": [
                {"type": "human", "content": "[2026-03-24T17:00:00Z] [Author: Серёга]: окей после пяти встречаемся"},
                {"type": "human", "content": "[2026-03-24T17:30:00Z] [Author: Лёня]: алло?"},
                {"type": "human", "content": "[2026-03-24T17:50:00Z] [Author: Лёня]: ну вы где"},
            ],
            "sender_id": "u_leo",
            "sender_name": "Лёня",
            "timestamp": "2026-03-24T18:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
    },
    # ── PUBLISH: Narrative of the past within future planning ─────────────
    {
        "description": "[TOOL=publish] Narrative of the past within future planning",
        "inputs": {
            "text": "в прошлый раз мы начали в 11 и не уложились до 13-ти,\nдавайте в этот раз возьмём с запасом — стартуем в 10",
            "history": [
                {"type": "human", "content": "[2026-03-24T10:45:00Z] [Author: PM]: нам нужно доделать то что не успели на прошлой неделе"},
                {"type": "human", "content": "[2026-03-24T10:52:00Z] [Author: Дима]: согласен, там осталось много"},
            ],
            "sender_id": "u_kate",
            "sender_name": "Катя",
            "timestamp": "2026-03-24T11:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "10:00", "city": None, "event_type": "встреча"}
            ],
            "comment": ""
        },
    },
    # ── PUBLISH: Translit/Slang 'poltretego' (14:30) ──────────────────────
    {
        "description": "[TOOL=publish] Russian translit 'poltretego' = 14:30",
        "inputs": {
            "text": "davay v poltretego, eto 14:30 da?",
            "history": [
                {"type": "human", "content": "[2026-03-24T14:22:00Z] [Author: Дэн]: vo skolko zavtra?"},
                {"type": "human", "content": "[2026-03-24T14:27:00Z] [Author: Артём]: я с утра занят"},
            ],
            "sender_id": "u_rustam",
            "sender_name": "Рустам",
            "timestamp": "2026-03-24T14:30:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "14:30", "city": None, "event_type": "встреча"}
            ],
            "comment": ""
        },
    },
    # ── PUBLISH: German idiom 'halb zehn' (09:30) ─────────────────────────
    {
        "description": "[MULTILANG] German idiom — 'halb zehn' = 09:30 (not 10:30)",
        "inputs": {
            "text": "morgen um halb zehn kurzes meeting ja?",
            "history": [
                {"type": "human", "content": "[2026-03-13T09:57:00Z] [Author: Anna]: wann treffen wir uns?"},
                {"type": "human", "content": "[2026-03-13T10:02:00Z] [Author: Klaus]: hab gerade mit dem Kunden gesprochen"},
            ],
            "sender_id": "803",
            "sender_name": "Klaus",
            "timestamp": "2026-03-13T10:05:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "09:30", "city": None, "event_type": "meeting"}
            ],
            "comment": ""
        },
    },
]


def main():
    client = Client()

    # Create or reuse dataset
    existing = {d.name: d for d in client.list_datasets()}
    if DATASET_NAME in existing:
        client.delete_dataset(dataset_name=DATASET_NAME)
        print(f"Deleted old dataset: {DATASET_NAME}")
        
    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description="Curated tool-call test cases for the event-detection agent (Native History)",
    )
    print(f"Created dataset: {DATASET_NAME}")

    # Add examples
    existing_descs = set()

    added = 0
    for ex in EXAMPLES:
        desc = ex["description"]
        if desc in existing_descs:
            print(f"  skip (exists): {desc}")
            continue
        client.create_example(
            dataset_id=dataset.id,
            inputs=ex["inputs"],
            outputs=ex["outputs"],
            metadata={"description": desc},
        )
        print(f"  added: {desc}")
        added += 1

    print(f"\nDone — {added} examples added to '{DATASET_NAME}'")
    print(f"View: https://eu.smith.langchain.com/datasets/{dataset.id}")


if __name__ == "__main__":
    main()
