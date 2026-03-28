import sys
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
load_dotenv()

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
            "sender_id": "304",
            "sender_name": "Elena"
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
            "sender_id": "u7",
            "sender_name": "Jane"
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
            "sender_id": "601",
            "sender_name": "Anton"
        },
        "metadata": {"group": "publish_simple", "split": "agent_behavior"}
    },
    {
        "description": (
            "F4: 'роберт давай встретимся в 10:30' — сообщение отправлено в 12:30. "
            "Тест проверяет, что модель НЕ отказывается публиковать событие только из-за того, "
            "что время сообщения (12:30) позже назначенной встречи (10:30). "
            "Модель не должна делать вывод 'встреча в прошлом — публиковать не имеет смысла'. "
            "Её задача — зафиксировать намерение, не рассуждать о том, реалистично ли оно."
        ),
        "inputs": {
            "text": "роберт давай встретимся в 10:30",
            "history": [],
            "sender_id": "u_ivan",
            "sender_name": "Иван",
            "timestamp": "2026-03-24T12:30:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "10:30", "city": None, "event_type": "встреча"}
            ],
            "sender_id": "u_ivan",
            "sender_name": "Иван"
        },
        "metadata": {"group": "publish_simple", "split": "agent_behavior"}
    },

    # --- Group G: Publish: context (group="publish_context") ---
    {
        "description": "G1: Вопросительная форма: 'сможете завтра в 14:30?'",
        "inputs": {
            "text": "сможете завтра в 14:30?",
            "history": [],
            "sender_id": "u_quest",
            "sender_name": "UserQuest",
            "timestamp": "2026-03-13T10:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "publish_event",
            "points": [
                {"time": "14:30", "city": None, "event_type": "встреча"}
            ],
            "sender_id": "u_quest",
            "sender_name": "UserQuest"
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
            "sender_id": "u_kate",
            "sender_name": "Катя"
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
            "sender_id": "u8",
            "sender_name": "Taylor"
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
            "sender_id": "201",
            "sender_name": "User",
            "timestamp": "2026-03-13T22:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": [],
            "sender_id": "201",
            "sender_name": "User"
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
            "sender_id": "502",
            "sender_name": "Vlad",
            "timestamp": "2026-03-13T10:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": [],
            "sender_id": "502",
            "sender_name": "Vlad"
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
            "sender_id": "u_leo",
            "sender_name": "Лёня",
            "timestamp": "2026-03-24T18:00:00Z",
        },
        "outputs": {
            "event": True,
            "points": [
                {
                    "city": None,
                    "event_type": "meeting",
                    "time": "17:30"
                }
            ],
            "tool": "publish_event",
            "sender_id": "u_leo",
            "sender_name": "Лёня"
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
                {"type": "tool", "content": "✅ Event published. event_ref: 1. Summary: разбор → 14:00", "tool_call_id": "tc1"},
            ],
            "sender_id": "u_nar",
            "sender_name": "UserNar",
            "timestamp": "2026-03-13T16:00:00Z",
        },
        "outputs": {
            "comment": "Updated duration: 14:00-15:30",
            "event": True,
            "event_ref": 1,
            "points": [
                {
                    "city": None,
                    "event_type": "разбор start",
                    "time": "14:00"
                },
                {
                    "city": None,
                    "event_type": "разбор end",
                    "time": "15:30"
                }
            ],
            "tool": "update_previous_event",
            "sender_id": "u_nar",
            "sender_name": "UserNar"
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
            "sender_id": "u_roma",
            "sender_name": "Рома",
            "timestamp": "2026-03-24T12:00:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": [],
            "sender_id": "u_roma",
            "sender_name": "Рома"
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
                {"type": "tool", "content": "✅ Event published. event_ref: 1. Summary: встреча → 15:00", "tool_call_id": "tc1"},
            ],
            "sender_id": "u_echo",
            "sender_name": "UserEcho",
            "timestamp": "2026-03-13T15:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event", 
            "points": [
                {"time": "15:00", "city": None, "event_type": "встреча"}
            ],
            "sender_id": "u_echo",
            "sender_name": "UserEcho",
            "comment": "confirmed"
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
            "sender_id": "802",
            "sender_name": "Степан",
            "timestamp": "2026-03-13T16:40:00Z",
        },
        "outputs": {
            "event": False,
            "tool": None,
            "points": [],
            "sender_id": "802",
            "sender_name": "Степан"
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
            "sender_id": "u2",
            "sender_name": "Петя",
            "comment": "UPDATE due to coordination"
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
            "sender_id": "u3",
            "sender_name": "Маша",
            "comment": "UPDATE due to coordination"
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
                {"type": "tool", "content": "✅ Event published. event_ref: 1071. Summary: star-fall start → 22:00, star-fall end → 06:00", "tool_call_id": "tc1"}
            ],
            "sender_id": "u_star",
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
            "sender_id": "u_star",
            "sender_name": "Anton",
            "comment": "added ISS pass at 03:00"
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
                {"type": "tool", "content": "✅ Event published. event_ref: 1. Summary: zoom → 09:00", "tool_call_id": "tc1"},
                {"type": "human", "content": "[2026-03-24T10:02:00Z] [Author: Jess]: можем в 11 если что?"},
                {"type": "ai", "tool_calls": [{"name": "update_previous_event", "args": {"event_ref": 1, "points": [{"time": "11:00", "city": None, "event_type": "zoom"}]}, "id": "tc2"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event updated. event_ref: 1. Summary: zoom → 11:00", "tool_call_id": "tc2"},
                {"type": "human", "content": "[2026-03-24T10:02:00Z] [Author: Jack]: давайте тогда в 12"},
                {"type": "ai", "tool_calls": [{"name": "update_previous_event", "args": {"event_ref": 1, "points": [{"time": "12:00", "city": None, "event_type": "zoom"}]}, "id": "tc3"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event updated. event_ref: 1. Summary: zoom → 12:00", "tool_call_id": "tc3"},
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
                {"time": "10:00", "city": None, "event_type": "zoom [UPDATED]"}
            ],
            "sender_id": "hr2",
            "sender_name": "Jane",
            "comment": "UPDATE due to coordination"
        },
        "metadata": {"group": "update_negotiation", "split": "agent_behavior"}
    },

    # --- Group L: Reference disambiguation (group="ref_disambiguation") ---
    # Both cases have TWO published events in history. The agent must pick the right event_ref.
    {
        "description": "L1: Two events — update the correct one by topic keyword ('митинг')",
        "inputs": {
            "text": "митинг перенесли на 11, опаздываю",
            "history": [
                {"type": "human", "content": "[2026-03-25T08:00:00Z] [Author: Lead]: завтра митинг в 9 утра"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"points": [{"time": "09:00", "city": None, "event_type": "митинг"}]}, "id": "tc_meet_1"}], "message_id": "m1"},
                {"type": "tool", "content": "✅ Event published. event_ref: 1010. Summary: митинг → 09:00", "tool_call_id": "tc_meet_1"},
                {"type": "human", "content": "[2026-03-25T08:05:00Z] [Author: PM]: и созвон в 14:00 не забудьте"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"points": [{"time": "14:00", "city": None, "event_type": "созвон"}]}, "id": "tc_sync_1"}], "message_id": "m2"},
                {"type": "tool", "content": "✅ Event published. event_ref: 2020. Summary: созвон → 14:00", "tool_call_id": "tc_sync_1"},
            ],
            "sender_id": "u_l1",
            "sender_name": "Петя",
            "timestamp": "2026-03-25T08:10:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "event_ref": 1010,
            "points": [{"time": "11:00", "city": None, "event_type": "митинг"}],
            "sender_id": "u_l1",
            "sender_name": "Петя",
            "comment": "UPDATE due to coordination"
        },
        "metadata": {"group": "ref_disambiguation", "split": "agent_behavior"}
    },
    {
        "description": "L2: Two events — update the correct one by explicit time reference ('созвон в 14')",
        "inputs": {
            "text": "созвон в 14 отменяется, переносим на 16",
            "history": [
                {"type": "human", "content": "[2026-03-26T09:00:00Z] [Author: Oleg]: стендап в 10 утра"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"points": [{"time": "10:00", "city": None, "event_type": "стендап"}]}, "id": "tc_stand_1"}], "message_id": "m3"},
                {"type": "tool", "content": "✅ Event published. event_ref: 3030. Summary: стендап → 10:00", "tool_call_id": "tc_stand_1"},
                {"type": "human", "content": "[2026-03-26T09:05:00Z] [Author: Dasha]: и созвон сегодня в 14"},
                {"type": "ai", "tool_calls": [{"name": "publish_event", "args": {"points": [{"time": "14:00", "city": None, "event_type": "созвон"}]}, "id": "tc_call_1"}], "message_id": "m4"},
                {"type": "tool", "content": "✅ Event published. event_ref: 4040. Summary: созвон → 14:00", "tool_call_id": "tc_call_1"},
            ],
            "sender_id": "u_l2",
            "sender_name": "Dasha",
            "timestamp": "2026-03-26T11:00:00Z",
        },
        "outputs": {
            "event": True,
            "tool": "update_previous_event",
            "event_ref": 4040,
            "points": [{"time": "16:00", "city": None, "event_type": "созвон"}],
            "sender_id": "u_l2",
            "sender_name": "Dasha",
            "comment": "UPDATE due to coordination"
        },
        "metadata": {"group": "ref_disambiguation", "split": "agent_behavior"}
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
