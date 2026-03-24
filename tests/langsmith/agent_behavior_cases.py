"""
agent_behavior_cases.py — LangSmith test cases for agent behavior (publish, update, no_publish).
Split: "agent_behavior"
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client

DATASET_NAME = "timezone-bot-agent-behavior"

EXAMPLES = [
    # --- Group F: Publish: simple (group="publish_simple") ---
    {
        "description": "F1: Availability window: 'I am free between 14:00 and 17:30'",
        "inputs": {
            "text": "I am free between 14:00 and 17:30 tomorrow",
            "history": [
                {"type": "human", "content": "[2026-03-13T09:48:00Z] [Author: Recruiter]: Hi Elena, when can we talk?"},
                {"type": "human", "content": "[2026-03-13T09:53:00Z] [Author: Elena]: Hi!"},
            ],
            "timestamp": "2026-03-13T10:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "14:00", "city": None, "event_type": "availability"},
                {"time": "17:30", "city": None, "event_type": "availability"}
            ]
        },
        "metadata": {"group": "publish_simple", "split": "agent_behavior"}
    },
    {
        "description": "F2: Dual timezone: 'sync at 9am EST, that's 2pm London'",
        "inputs": {
            "text": "sync tomorrow at 9am EST, that's 2pm London",
            "history": [
                {"type": "human", "content": "[2026-03-20T17:55:00Z] [Author: Lead]: include US colleagues please"}
            ],
            "timestamp": "2026-03-20T18:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "14:00", "city": "London", "event_type": "sync"}
            ]
        },
        "metadata": {"group": "publish_simple", "split": "agent_behavior"}
    },
    {
        "description": "F3: Stress test: 3 events in one message",
        "inputs": {
            "text": "Man sry for writing so late im just buried in work... about the loogistics call lets do thursdsy at 10:30... talk about the investor deck on Friday at 1 PM... code deadline on Monday by 5 PM",
            "history": [
                {"type": "human", "content": "[2026-03-13T21:15:00Z] [Author: Dima]: Hey colleagues..."},
                {"type": "human", "content": "[2026-03-13T21:30:00Z] [Author: Elena]: Agree... How about Thursday morning, say half past nine?"},
            ],
            "timestamp": "2026-03-13T22:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "10:30", "city": None, "event_type": "logistics call"},
                {"time": "13:00", "city": None, "event_type": "investor deck"},
                {"time": "17:00", "city": None, "event_type": "code deadline"}
            ]
        },
        "metadata": {"group": "publish_simple", "split": "agent_behavior"}
    },

    # --- Group G: Publish: context (group="publish_context") ---
    {
        "description": "G1: Вопросительная форма: 'сможете завтра в 14:30?'",
        "inputs": {
            "text": "сможете завтра в 14:30?",
            "history": [],
            "timestamp": "2026-03-13T10:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "14:30", "city": None, "event_type": "встреча"}
            ]
        },
        "metadata": {"group": "publish_context", "split": "agent_behavior"}
    },
    {
        "description": "G2: Нарратив прошлого: 'в прошлый раз в 11 не успели — стартуем в 10'",
        "inputs": {
            "text": "в прошлый раз мы начали в 11 и не уложились до 13-ти, давайте в этот раз возьмём с запасом — стартуем в 10",
            "history": [
                {"type": "human", "content": "[2026-03-24T10:45:00Z] [Author: PM]: нам нужно доделать то что не успели на прошлой неделе"},
            ],
            "timestamp": "2026-03-24T11:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "10:00", "city": None, "event_type": "встреча"}
            ]
        },
        "metadata": {"group": "publish_context", "split": "agent_behavior"}
    },
    {
        "description": "G3: Отвлекающие времена в истории: Board Meeting 5pm",
        "inputs": {
            "text": "Actually, let's hop on a quick sync for the Board Meeting at 5pm today.",
            "history": [
                {"type": "human", "content": "[2026-03-22T09:30:00Z] [Author: Alex]: COB today at 11 for sure."},
                {"type": "human", "content": "[2026-03-22T13:30:00Z] [Author: Taylor]: ping"},
            ],
            "timestamp": "2026-03-22T14:40:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "17:00", "city": None, "event_type": "Board Meeting"}
            ]
        },
        "metadata": {"group": "publish_context", "split": "agent_behavior"}
    },

    # --- Group H: No publish (group="no_publish") ---
    {
        "description": "H1: Личный план (Personal plan)",
        "inputs": {
            "text": "Я пойду спать в 11 вечера",
            "history": [
                {"type": "human", "content": "[2026-03-13T21:50:00Z] [Author: User1]: Ох, устал сегодня."}
            ],
            "timestamp": "2026-03-13T22:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
        "metadata": {"group": "no_publish", "trap": True, "split": "agent_behavior"}
    },
    {
        "description": "H2: Прошедшее простое (Past event mention)",
        "inputs": {
            "text": "вчерашний созвон в 11 утра затянулся до обеда",
            "history": [
                {"type": "human", "content": "[2026-03-13T09:45:00Z] [Author: Team]: Планируем ретроспективу."}
            ],
            "timestamp": "2026-03-13T10:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
        "metadata": {"group": "no_publish", "trap": True, "split": "agent_behavior"}
    },
    {
        "description": "H3: Постфактум-жалоба (Post-factum complaint)",
        "inputs": {
            "text": "мы же договорились в 17:30, я прождал полчаса",
            "history": [
                {"type": "human", "content": "[2026-03-24T17:00:00Z] [Author: Серёга]: окей после пяти встречаемся"},
                {"type": "human", "content": "[2026-03-24T17:30:00Z] [Author: Лёня]: алло?"},
            ],
            "timestamp": "2026-03-24T18:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
        "metadata": {"group": "no_publish", "trap": True, "split": "agent_behavior"}
    },
    {
        "description": "H4: Post-event narrative: 'с двух до 15:30 разбирали'",
        "inputs": {
            "text": "с двух до 15:30 разбирали",
            "history": [
                {"type": "human", "content": "[2026-03-13T13:45:00Z] [Author: User1]: встречаемся в 14:00 для разбора"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"points": [{"time": "14:00", "city": None, "event_type": "разбор"}]}, "id": "tc1"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1", "tool_call_id": "tc1"},
            ],
            "timestamp": "2026-03-13T16:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
        "metadata": {"group": "no_publish", "trap": True, "split": "agent_behavior"}
    },
    {
        "description": "H5: Сарказм: 'ровно в полночь, как в сказке' 🙄",
        "inputs": {
            "text": "да-да, договорились — ровно в полночь, как в сказке 🙄",
            "history": [
                {"type": "human", "content": "[2026-03-24T11:50:00Z] [Author: Толя]: может в следующем году?"},
            ],
            "timestamp": "2026-03-24T12:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
        "metadata": {"group": "no_publish", "trap": True, "split": "agent_behavior"}
    },
    {
        "description": "H6: Эхо-подтверждение (Echo confirmation)",
        "inputs": {
            "text": "отлично, до завтра в 15 как договорились",
            "history": [
                {"type": "human", "content": "[2026-03-13T14:45:00Z] [Author: Anton]: завтра в 15:00 встречаемся"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"points": [{"time": "15:00", "city": None, "event_type": "встреча"}]}, "id": "tc1"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1", "tool_call_id": "tc1"},
            ],
            "timestamp": "2026-03-13T15:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
        "metadata": {"group": "no_publish", "trap": True, "split": "agent_behavior"}
    },
    {
        "description": "H7: Числовая ловушка: 'встречаемся в девятом' (building)",
        "inputs": {
            "text": "встречаемся в девятом",
            "history": [
                {"type": "human", "content": "[2026-03-13T16:30:00Z] [Author: Гоша]: в каком здании встречаемся?"},
            ],
            "timestamp": "2026-03-13T16:40:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": []
        },
        "metadata": {"group": "no_publish", "trap": True, "split": "agent_behavior"}
    },

    # --- Group I: Update: corrections (group="update_correction") ---
    {
        "description": "I1: Прямая замена: 'нет давай в 11, у меня в 10 другой звонок'",
        "inputs": {
            "text": "нет давай лучше в 11, у меня в 10 другой звонок",
            "history": [
                {"type": "human", "content": "[2026-03-20T09:00:00Z] [Author: Иван]: созвон в 10 утра?"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"points": [{"time": "10:00", "city": None, "event_type": "созвон"}]}, "id": "tc1"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1", "tool_call_id": "tc1"}
            ],
            "timestamp": "2026-03-20T09:10:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "event_ref": 1,
            "points": [
                {"time": "11:00", "city": None, "event_type": "созвон"}
            ]
        },
        "metadata": {"group": "update_correction", "split": "agent_behavior"}
    },
    {
        "description": "I2: Финал торга: 'ок, в полвторого договорились'",
        "inputs": {
            "text": "ок, тогда в полвторого договорились",
            "history": [
                {"type": "human", "content": "[2026-03-20T10:00:00Z] [Author: Маша]: встреча в 14:00?"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"points": [{"time": "14:00", "city": None, "event_type": "встреча"}]}, "id": "tc1"}], "message_id": "m2"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1", "tool_call_id": "tc1"},
                {"type": "human", "content": "[2026-03-20T10:05:00Z] [Author: Саша]: я не успею к 14, можно в 13:30?"}
            ],
            "timestamp": "2026-03-20T10:20:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "event_ref": 1,
            "points": [
                {"time": "13:30", "city": None, "event_type": "встреча"}
            ]
        },
        "metadata": {"group": "update_correction", "split": "agent_behavior"}
    },

    # --- Group J: Update: additions (group="update_addition") ---
    {
        "description": "J1: Add ISS passing to star-fall event",
        "inputs": {
            "text": "and approximately at 3 it,s possible to watch ISS pasing",
            "history": [
                {"type": "human", "content": "[2026-03-23T20:10:00Z] [Author: Anton]: in our rigion it will be star-fall from 10 to 6"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"points": [{"time": "22:00", "city": None, "event_type": "star-fall start"}, {"time": "06:00", "city": None, "event_type": "star-fall end"}]}, "id": "tc1"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1071", "tool_call_id": "tc1"}
            ],
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
            ]
        },
        "metadata": {"group": "update_addition", "split": "agent_behavior"}
    },

    # --- Group K: Update: complex disputes (group="update_negotiation") ---
    {
        "description": "K1: Многоитерационный торг: 'нет я настаиваю на том что в 10'",
        "inputs": {
            "text": "нет я настаиваю на том что нам стоит собраться в 10",
            "history": [
                {"type": "human", "content": "[2026-03-24T09:58:00Z] [Author: Jack]: давайте общий зум по scope of work завтра в 9 утра"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"points": [{"time": "09:00", "city": None, "event_type": "zoom"}]}, "id": "tc1"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1", "tool_call_id": "tc1"},
                {"type": "human", "content": "[2026-03-24T10:02:00Z] [Author: Jess]: можем в 11 если что?"},
                {"type": "ai", "tool_calls": [{"name": "update_previous_event", "args": {"event_ref": 1, "points": [{"time": "11:00", "city": None, "event_type": "zoom"}]}, "id": "tc2"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event updated. event_ref: 1", "tool_call_id": "tc2"},
                {"type": "human", "content": "[2026-03-24T10:02:00Z] [Author: Jack]: давайте тогда в 12"},
                {"type": "ai", "tool_calls": [{"name": "update_previous_event", "args": {"event_ref": 1, "points": [{"time": "12:00", "city": None, "event_type": "zoom"}]}, "id": "tc3"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event updated. event_ref: 1", "tool_call_id": "tc3"},
            ],
            "timestamp": "2026-03-24T10:15:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "event_ref": 1,
            "points": [
                {"time": "10:00", "city": None, "event_type": "zoom [UPDATED]"}
            ]
        },
        "metadata": {"group": "update_negotiation", "split": "agent_behavior"}
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
        description="Agent behavior test cases (publish, update, no_publish)",
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
