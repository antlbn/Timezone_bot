import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.event_detection.detector import detect_event

async def mock_send(text):
    print(f"BOT SENT: {text}")
    return "msg_id_1"

async def mock_edit(msg_id, text):
    print(f"BOT EDITED {msg_id}: {text}")

async def main():
    chat_id = "test_chat_1"
    
    # 1. Star fall
    res1 = await detect_event(
        current_msg={
            "author_id": "anton",
            "author_name": "Anton Lubny",
            "text": "in our rigion it will be star-fall from 10 to 6",
            "timestamp_utc": "2026-03-23T20:54:00Z"
        },
        snapshot=[],
        sender_db={"timezone": "Europe/London", "city": "London", "flag": "GB"},
        send_fn=mock_send,
        edit_fn=mock_edit,
        platform="discord",
        chat_id=chat_id,
    )
    print("Res1 Tool:", res1.get("tool_used"), "Points:", res1.get("points"))
    
    # 2. ISS
    res2 = await detect_event(
        current_msg={
            "author_id": "anton",
            "author_name": "Anton Lubny",
            "text": "and approximately at 3 it,s possible to watch ISS pasing",
            "timestamp_utc": "2026-03-23T20:55:00Z"
        },
        snapshot=[],
        sender_db={"timezone": "Europe/London", "city": "London", "flag": "GB"},
        send_fn=mock_send,
        edit_fn=mock_edit,
        platform="discord",
        chat_id=chat_id,
    )
    print("Res2 Tool:", res2.get("tool_used"), "Points:", res2.get("points"))
    print("Res2 Event Ref:", res2.get("event_ref"))

if __name__ == "__main__":
    asyncio.run(main())
