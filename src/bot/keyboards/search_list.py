from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData


class SearchCallback(CallbackData, prefix="search"):
    action: str
    search_id: str


def search_list_keyboard(user_searches: list) -> InlineKeyboardMarkup:
    """Generates a keyboard with a delete button for each search."""
    keyboard_buttons = []
    
    for search in user_searches:
        # Create a callback button with our factory.
        # This is type-safe and easy to parse.
        callback_data = SearchCallback(
            action="delete",
            search_id=search["id"]
        ).pack()  # .pack() serializes it into a string for Telegram

        keyboard_buttons.append(
            [InlineKeyboardButton(text=f"❌ {search['name']}", callback_data=callback_data)]
        )

    # Add a "back" button to the menu
    keyboard_buttons.append(
        [InlineKeyboardButton(text="⬅️ חזרה לתפריט", callback_data="start_menu")]
    )
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)