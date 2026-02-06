"""
Discord State Machine - simple in-memory state tracking for user conversations.
"""
from typing import Dict, Optional

# In-memory state storage: {user_id: state_data}
_user_states: Dict[int, dict] = {}


def set_state(user_id: int, state: str, **data) -> None:
    """Set user's current state with optional data."""
    _user_states[user_id] = {"state": state, **data}


def get_state(user_id: int) -> Optional[dict]:
    """Get user's current state data, or None if not set."""
    return _user_states.get(user_id)


def clear_state(user_id: int) -> None:
    """Clear user's state."""
    _user_states.pop(user_id, None)


def is_waiting_fallback(user_id: int) -> bool:
    """Check if user is waiting for fallback input."""
    data = get_state(user_id)
    return data is not None and data.get("state") == "waiting_for_fallback"
