"""
In-Memory Pending Storage (Layer 4 of Working Memory).
Stores messages for users currently in the onboarding flow.
Replaces Redis-based storage.

Single-process runtime only: module-level state is not shared across worker
processes. A PID guard clears inherited state after fork-like process changes
so stale queues do not silently leak into child processes.
"""

import asyncio
import os
import time
from src.config import get_onboarding_timeout
from src.logger import get_logger

logger = get_logger()

# Structure: {(user_id, platform): {"messages": List[dict], "expires": float}}
_frozen_messages = {}
_runtime_pid = os.getpid()


def _ensure_process_local_state() -> None:
    """Reset inherited in-memory state if the current PID changed."""
    global _runtime_pid, _on_expire_callback

    current_pid = os.getpid()
    if current_pid == _runtime_pid:
        return

    logger.warning(
        "Pending storage detected PID change (%s -> %s); clearing inherited in-memory state. "
        "This module requires a single-process runtime per worker.",
        _runtime_pid,
        current_pid,
    )
    _frozen_messages.clear()
    _dm_invite_timestamps.clear()
    _on_expire_callback = None
    _runtime_pid = current_pid


async def save_pending_message(user_id: int, platform: str, message_data: dict):
    """
    Save message data to in-memory 'frozen' storage for onboarding.
    Appends if entry exists and is not expired.
    """
    _ensure_process_local_state()
    key = (user_id, platform)
    timeout = get_onboarding_timeout()
    now = time.time()

    if key in _frozen_messages and now < _frozen_messages[key]["expires"]:
        # Entry exists and is fresh — just append
        _frozen_messages[key]["messages"].append(message_data)
        logger.info(
            f"Appended pending message for {user_id} ({platform}). Total: {len(_frozen_messages[key]['messages'])}"
        )
    else:
        # Create new entry or replace expired one
        _frozen_messages[key] = {"messages": [message_data], "expires": now + timeout}
        logger.info(
            f"Started new pending queue for {user_id} ({platform}). TTL: {timeout}s."
        )


async def get_and_delete_pending_messages(user_id: int, platform: str) -> list[dict]:
    """
    Retrieve and remove ALL pending messages for a user.
    Checks for expiration.
    """
    _ensure_process_local_state()
    key = (user_id, platform)
    if key not in _frozen_messages:
        return []

    item = _frozen_messages.pop(key)
    if time.time() > item["expires"]:
        logger.warning(f"Pending messages for {user_id} ({platform}) expired.")
        return []

    return item["messages"]


async def peek_pending_messages(user_id: int, platform: str) -> list[dict]:
    """
    Look at pending messages without deleting them.
    Checks for expiration.
    """
    _ensure_process_local_state()
    key = (user_id, platform)
    if key not in _frozen_messages:
        return []

    item = _frozen_messages[key]
    if time.time() > item["expires"]:
        return []

    return item["messages"]


# Track when we last sent a DM invite to avoid spamming: {(user_id, platform): timestamp}
_dm_invite_timestamps: dict[tuple[int, str], float] = {}


async def should_send_dm_invite(user_id: int, platform: str, cooldown: int) -> bool:
    """Check if enough time has passed since we last invited this user to DM onboarding."""
    _ensure_process_local_state()
    key = (user_id, platform)
    last_sent = _dm_invite_timestamps.get(key, 0)
    return (time.time() - last_sent) >= cooldown


async def mark_dm_invite_sent(user_id: int, platform: str):
    """Record that we just sent a DM onboarding invite to this user."""
    _ensure_process_local_state()
    _dm_invite_timestamps[(user_id, platform)] = time.time()


async def clear_dm_invite(user_id: int, platform: str):
    """Clear the DM invite cooldown for a user (e.g. after successful onboarding)."""
    _ensure_process_local_state()
    _dm_invite_timestamps.pop((user_id, platform), None)


# Callback for processing expired messages: func(user_id, platform, messages)
_on_expire_callback = None


def set_on_expire_callback(callback):
    """Register a callback for processing expired pending messages."""
    _ensure_process_local_state()
    global _on_expire_callback
    _on_expire_callback = callback


async def cleanup_loop(bot=None):
    """
    Background task to clean up expired frozen messages and stale invite timestamps.
    Expired messages are passed to the global callback for final 'unlocked' processing.
    """
    _ensure_process_local_state()
    logger.info("Pending storage cleanup loop started.")
    while True:
        await asyncio.sleep(60)
        _ensure_process_local_state()
        now = time.time()

        # 1. Handle expired frozen messages (onboarding timeouts)
        to_process = []
        for k, v in _frozen_messages.items():
            if now > v["expires"]:
                to_process.append((k, v["messages"]))

        for k, messages in to_process:
            _frozen_messages.pop(k, None)
            logger.info(
                f"Pending messages for user {k[0]} ({k[1]}) timed out. Dispatching timeout handler."
            )

            if _on_expire_callback:
                try:
                    # Execute callback (should be a non-blocking or task-creating function)
                    if asyncio.iscoroutinefunction(_on_expire_callback):
                        asyncio.create_task(
                            _on_expire_callback(bot, k[0], k[1], messages)
                        )
                    else:
                        _on_expire_callback(bot, k[0], k[1], messages)
                except Exception as e:
                    logger.error(f"Error in pending expire callback: {e}")

        # 2. Clean up very old invite timestamps (> 24h)
        stale_invites = [
            k for k, ts in _dm_invite_timestamps.items() if (now - ts) > 86400
        ]
        for k in stale_invites:
            _dm_invite_timestamps.pop(k, None)
