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

    # ── PUBLISH: первое упоминание встречи ─────────────────────────────────
    {
        "description": "[TOOL=publish] First meeting mention",
        "inputs": {
            "text": "Давайте созвонимся завтра в 10 утра",
            "history": [],
            "sender_id": "u1",
            "sender_name": "Иван",
            "timestamp": "2026-03-20T09:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "time": "10:00",
        },
    },

    # ── PUBLISH: deadline with slang ───────────────────────────────────────
    {
        "description": "[TOOL=publish] Deadline with slang time",
        "inputs": {
            "text": "gotta ship the press release by 8 tonight ngl",
            "history": [
                {"type": "human", "content": "[2026-03-20T15:15:00Z] [Jane]: any updates on the release?"},
                {"type": "human", "content": "[2026-03-20T15:20:00Z] [Anton]: still waiting on sign-off"}
            ],
            "sender_id": "u2",
            "sender_name": "Anton",
            "timestamp": "2026-03-20T15:30:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "time": "20:00",
        },
    },

    # ── UPDATE: коррекция времени (user2 corrects what bot already posted) ─
    {
        "description": "[TOOL=update] User corrects previously proposed time",
        "inputs": {
            "text": "нет давай лучше в 11, у меня в 10 другой звонок",
            "history": [
                {"type": "human", "content": "[2026-03-20T09:00:00Z] [Иван]: созвон в 10 утра?"},
                {"type": "ai", "content": "[BOT]: detected: созвон → 10:00", "message_id": "m1"}
            ],
            "sender_id": "u2",
            "sender_name": "Петя",
            "timestamp": "2026-03-20T09:10:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "time": "11:00",
        },
    },

    # ── UPDATE: согласование после торга ──────────────────────────────────
    {
        "description": "[TOOL=update] Negotiation resolves to new time",
        "inputs": {
            "text": "ок, тогда в полвторого договорились",
            "history": [
                {"type": "human", "content": "[2026-03-20T10:00:00Z] [Маша]: встреча в 14:00?"},
                {"type": "ai", "content": "[BOT]: detected: встреча → 14:00", "message_id": "m2"},
                {"type": "human", "content": "[2026-03-20T10:05:00Z] [Саша]: я не успею к 14, можно в 13:30?"}
            ],
            "sender_id": "u3",
            "sender_name": "Маша",
            "timestamp": "2026-03-20T10:20:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "time": "13:30",
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
            "time": None,
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
            "time": None,
        },
    },

    # ── PUBLISH: explicit city / timezone ─────────────────────────────────
    {
        "description": "[TOOL=publish] Explicit city — take London time",
        "inputs": {
            "text": "sync tomorrow at 9am EST, that's 2pm London",
            "history": [
                {"type": "human", "content": "[2026-03-20T17:55:00Z] [Lead]: include US colleagues please"}
            ],
            "sender_id": "u7",
            "sender_name": "Jane",
            "timestamp": "2026-03-20T18:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "time": "14:00",
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
