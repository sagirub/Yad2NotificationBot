from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ הוסף חיפוש חדש", callback_data="add_search")],
        [InlineKeyboardButton(text="📋 צפה בחיפושים", callback_data="view_searches")],
    ])
