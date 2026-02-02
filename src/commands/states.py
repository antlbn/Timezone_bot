from aiogram.fsm.state import State, StatesGroup

class SetTimezone(StatesGroup):
    """FSM states for /tb_settz flow."""
    waiting_for_city = State()
    waiting_for_time = State()  # Fallback when city not found

class RemoveMember(StatesGroup):
    """FSM states for /tb_remove flow."""
    waiting_for_number = State()
