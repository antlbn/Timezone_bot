from src.storage import storage
from src.transform import get_utc_offset


async def get_sorted_chat_members(chat_id: int | str, platform: str):
    """
    Fetch all members of a chat and sort them by UTC offset.
    Common logic used by both Discord and Telegram.
    """
    members = await storage.get_chat_members(int(chat_id), platform=platform)
    if not members:
        return []

    # Sort by UTC offset
    members.sort(key=lambda m: get_utc_offset(m["timezone"]))
    return members
