import time


ACTIVITY_FLUSH_INTERVAL_SECONDS = 300.0
_last_activity_flush: dict[tuple[int, str], float] = {}


def should_flush_activity(user_id: int, platform: str) -> bool:
    """Throttle write-heavy activity updates on chatty message streams."""
    key = (user_id, platform)
    now = time.monotonic()
    last_flush = _last_activity_flush.get(key)
    if last_flush is not None and (now - last_flush) < ACTIVITY_FLUSH_INTERVAL_SECONDS:
        return False

    _last_activity_flush[key] = now
    return True


def reset_activity_throttle(user_id: int, platform: str) -> None:
    """Clear throttling state for callers that explicitly want an immediate flush."""
    _last_activity_flush.pop((user_id, platform), None)
