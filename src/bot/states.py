from aiogram.fsm.state import State, StatesGroup

class AddSearch(StatesGroup):
    waiting_for_link = State()
    waiting_for_commercial_filter = State()  # Ask if user wants to exclude commercial items
    waiting_for_name = State()