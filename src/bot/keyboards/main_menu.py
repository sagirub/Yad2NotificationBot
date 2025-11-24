from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add new search", callback_data="add_search")],
        [InlineKeyboardButton(text="📋 View searches", callback_data="view_searches")],
    ])
