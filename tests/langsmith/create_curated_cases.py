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

from langsmith import Client

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

    # ── NO EVENT: casual chat ──────────────────────────────────────────────
    {
        "description": "[TOOL=null] Casual message — no event",
        "inputs": {
            "text": "Привет, как дела?",
            "history": [],
            "sender_id": "u1",
            "sender_name": "User",
            "timestamp": "2026-03-20T12:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
    },

    # ── NO EVENT: day-of-week misread trap ────────────────────────────────
    {
        "description": "[TOOL=null] Day-of-week not a time (regression)",
        "inputs": {
            "text": "Увидимся в пятницу, пока без конкретного времени",
            "history": [],
            "sender_id": "u1",
            "sender_name": "User",
            "timestamp": "2026-03-20T10:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
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
