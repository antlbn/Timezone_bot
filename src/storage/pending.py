"""
Invite cooldown helpers for onboarding prompts.

The old pending-message queue was removed. We now only track whether a user
was invited recently so the bot does not spam onboarding prompts.
"""

import time

# Track when we last sent an onboarding invite: {(user_id, platform): timestamp}
_dm_invite_timestamps: dict[tuple[int, str], float] = {}


async def should_send_dm_invite(user_id: int, platform: str, cooldown: int) -> bool:
    """Check if enough time has passed since the last onboarding invite."""
    key = (user_id, platform)
    last_sent = _dm_invite_timestamps.get(key, 0)
    return (time.time() - last_sent) >= cooldown


async def mark_dm_invite_sent(user_id: int, platform: str):
    """Record that an onboarding invite was sent just now."""
    _dm_invite_timestamps[(user_id, platform)] = time.time()


async def clear_dm_invite(user_id: int, platform: str):
    """Clear invite cooldown for a user."""
    _dm_invite_timestamps.pop((user_id, platform), None)
