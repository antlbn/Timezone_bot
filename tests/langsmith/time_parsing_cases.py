"""
time_parsing_cases.py — LangSmith test cases for time extraction.
Split: "time_parsing"
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client

DATASET_NAME = "timezone-bot-time-parsing"

EXAMPLES = [
    # --- Group A: Standard formats (group="standard") ---
    {
        "description": "A1: созвониться в 15:00 сегодня?",
        "inputs": {
            "text": "созвониться в 15:00 сегодня?",
            "history": [],
            "sender_id": "999",
            "sender_name": "TestUser",
            "timestamp": "2026-03-13T10:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "15:00", "city": None, "event_type": "созвон"}
            ],
            "sender_id": "999",
            "sender_name": "TestUser"
        },
        "metadata": {"group": "standard", "split": "time_parsing"}
    },
    {
        "description": "A2: sync at 2pm today",
        "inputs": {
            "text": "sync at 2pm today",
            "history": [],
            "timestamp": "2026-03-13T10:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "14:00", "city": None, "event_type": "sync"}
            ]
        },
        "metadata": {"group": "standard", "split": "time_parsing"}
    },
    {
        "description": "A3: гы народ митос завтр в 1500 не проспите лан?",
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
            ]
        },
        "metadata": {"group": "standard", "split": "time_parsing"}
    },
    {
        "description": "A4: gotta ship the press release by 8 tonight ngl",
        "inputs": {
            "text": "gotta ship the press release by 8 tonight ngl",
            "history": [
                {"type": "human", "content": "[2026-03-13T15:15:00Z] [Author: Jane]: any updates on the release?"},
                {"type": "human", "content": "[2026-03-13T15:20:00Z] [Author: Anton]: still waiting on sign-off"}
            ],
            "sender_id": "u2",
            "sender_name": "Anton",
            "timestamp": "2026-03-13T15:30:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "20:00", "city": None, "event_type": "deadline"}
            ]
        },
        "metadata": {"group": "standard", "split": "time_parsing"}
    },

    # --- Group B: Idioms (group="idioms") ---
    {
        "description": "B1: встречаемся без четверти шесть у входа",
        "inputs": {
            "text": "встречаемся без четверти шесть у входа",
            "history": [
                {"type": "human", "content": "[2026-03-13T17:15:00Z] [Author: Anton]: Ребят, во сколько сегодня встреча?"}
            ],
            "timestamp": "2026-03-13T17:20:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "17:45", "city": None, "event_type": "встреча"}
            ]
        },
        "metadata": {"group": "idioms", "split": "time_parsing"}
    },
    {
        "description": "B2: ок, тогда в полвторого договорились",
        "inputs": {
            "text": "ок, тогда в полвторого договорились",
            "history": [
                {"type": "human", "content": "[2026-03-13T10:00:00Z] [Author: Маша]: встреча в 14:00?"},
                {"type": "human", "content": "[2026-03-13T10:05:00Z] [Author: Саша]: я не успею к 14, можно в 13:30?"}
            ],
            "timestamp": "2026-03-13T10:20:00Z",
        },
        "outputs": {
            "event": True,
            # Note: User schema says this should be 13:30
            "points": [
                {"time": "13:30", "city": None, "event_type": "встреча"}
            ]
        },
        "metadata": {"group": "idioms", "split": "time_parsing"}
    },
    {
        "description": "B3: завтра в час ждём всех (timestamp 23:50)",
        "inputs": {
            "text": "завтра в час ждём всех",
            "history": [],
            "timestamp": "2026-03-13T23:50:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "13:00", "city": None, "event_type": "встреча"}
            ]
        },
        "metadata": {"group": "idioms", "split": "time_parsing"}
    },
    {
        "description": "B4: morgen um halb zehn kurzes meeting ja?",
        "inputs": {
            "text": "morgen um halb zehn kurzes meeting ja?",
            "history": [],
            "timestamp": "2026-03-13T10:05:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "09:30", "city": None, "event_type": "meeting"}
            ]
        },
        "metadata": {"group": "idioms", "split": "time_parsing"}
    },
    {
        "description": "B5: réunion demain matin à 9h",
        "inputs": {
            "text": "réunion demain matin à 9h",
            "history": [],
            "timestamp": "2026-03-13T14:33:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "09:00", "city": None, "event_type": "réunion"}
            ]
        },
        "metadata": {"group": "idioms", "split": "time_parsing"}
    },
    {
        "description": "B6: дедлайн сегодня в полночь",
        "inputs": {
            "text": "дедлайн сегодня в полночь",
            "history": [],
            "timestamp": "2026-03-13T12:00:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "00:00", "city": None, "event_type": "дедлайн"}
            ]
        },
        "metadata": {"group": "idioms", "split": "time_parsing"}
    },

    # --- Group C: Relative (group="relative") ---
    {
        "description": "C1: через час будет созвон (ts 12:21)",
        "inputs": {
            "text": "через час будет созвон",
            "history": [],
            "timestamp": "2026-03-13T12:21:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "13:21", "city": None, "event_type": "созвон"}
            ]
        },
        "metadata": {"group": "relative", "split": "time_parsing"}
    },
    {
        "description": "C2: чз 20 мин хопа в зуме ладн (ts 11:47)",
        "inputs": {
            "text": "чз 20 мин хопа в зуме ладн",
            "history": [],
            "timestamp": "2026-03-13T11:47:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "12:07", "city": None, "event_type": "встреча"}
            ]
        },
        "metadata": {"group": "relative", "split": "time_parsing"}
    },

    # --- Group D: Typos and translit (group="typos") ---
    {
        "description": "D1: lets do thursdsy at 10:30",
        "inputs": {
            "text": "lets do thursdsy at 10:30",
            "history": [],
            "timestamp": "2026-03-13T10:00:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "10:30", "city": None, "event_type": "meeting"}
            ]
        },
        "metadata": {"group": "typos", "split": "time_parsing"}
    },
    {
        "description": "D2: встречаемся бес четверти шесть",
        "inputs": {
            "text": "встречаемся бес четверти шесть",
            "history": [
                {"type": "human", "content": "[2026-03-13T17:15:00Z] [Author: Anton]: Ребят, во сколько сегодня встреча?"}
            ],
            "timestamp": "2026-03-13T17:20:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "17:45", "city": None, "event_type": "встреча"}
            ]
        },
        "metadata": {"group": "typos", "split": "time_parsing"}
    },
    {
        "description": "D3: davay v poltretego",
        "inputs": {
            "text": "davay v poltretego",
            "history": [],
            "timestamp": "2026-03-24T14:30:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "14:30", "city": None, "event_type": "встреча"}
            ]
        },
        "metadata": {"group": "typos", "split": "time_parsing"}
    },
    {
        "description": "D4: and approximately at 3 it,s possible to watch ISS pasing",
        "inputs": {
            "text": "and approximately at 3 it,s possible to watch ISS pasing",
            "history": [],
            "timestamp": "2026-03-23T20:12:26Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "03:00", "city": None, "event_type": "ISS passing"}
            ]
        },
        "metadata": {"group": "typos", "split": "time_parsing"}
    },

    # --- Group E: Self-correction (group="self_correction") ---
    {
        "description": "E1: meeting is at 7 in evening i mean 7pm not morning lol",
        "inputs": {
            "text": "meeting is at 7 in evening i mean 7pm not morning lol",
            "history": [],
            "timestamp": "2026-03-13T09:15:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "19:00", "city": None, "event_type": "meeting"}
            ]
        },
        "metadata": {"group": "self_correction", "split": "time_parsing"}
    },
    {
        "description": "E2: чз полчаса хопа в зуме ладн? ой сорян имел в виду не щас а в 1430",
        "inputs": {
            "text": "чз полчаса хопа в зуме ладн? ой сорян имел в виду не щас а в 1430",
            "history": [],
            "timestamp": "2026-03-13T13:00:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "14:30", "city": None, "event_type": "встреча"}
            ]
        },
        "metadata": {"group": "self_correction", "split": "time_parsing"}
    },
    {
        "description": "E3: mañana a las 9 y media, no a las 10 como dije antes",
        "inputs": {
            "text": "mañana a las 9 y media, no a las 10 como dije antes",
            "history": [],
            "timestamp": "2026-03-13T17:02:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {"time": "09:30", "city": None, "event_type": "reunión"}
            ]
        },
        "metadata": {"group": "self_correction", "split": "time_parsing"}
    },
]

def main():
    client = Client()
    existing = {d.name: d for d in client.list_datasets()}
    if DATASET_NAME in existing:
        client.delete_dataset(dataset_name=DATASET_NAME)
        print(f"Deleted old dataset: {DATASET_NAME}")
        
    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description="Time parsing test cases sorted by group",
    )
    print(f"Created dataset: {DATASET_NAME}")

    added = 0
    for ex in EXAMPLES:
        client.create_example(
            dataset_id=dataset.id,
            inputs=ex["inputs"],
            outputs=ex["outputs"],
            metadata=ex["metadata"],
        )
        added += 1

    print(f"\nDone — {added} examples added to '{DATASET_NAME}'")
    print(f"View: https://eu.smith.langchain.com/datasets/{dataset.id}")

if __name__ == "__main__":
    main()
