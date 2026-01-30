from aiogram import F, Router, types

from src.bot.keyboards.search_list import SearchCallback, search_list_keyboard
from src.bot.db import get_searches, delete_search

router = Router()

@router.callback_query(F.data == "view_searches")
async def cb_view_searches(callback: types.CallbackQuery):
    """Shows all active searches with 'Delete' buttons."""
    user_id = str(callback.from_user.id)
    
    # --- Get from Database ---
    searches = await get_searches(user_id)
    # --- End Database Logic ---
    
    if not searches:
        await callback.message.answer("אין לך חיפושים עדיין.")
    else:
        await callback.message.answer(
            "החיפושים שלך:",
            reply_markup=search_list_keyboard(searches)
        )
    await callback.answer()

@router.callback_query(SearchCallback.filter(F.action == "delete"))
async def cb_delete_search(callback: types.CallbackQuery, callback_data: SearchCallback):
    """
    Handles the 'Delete' button press using the CallbackData factory.
    `aiogram` automatically unpacks the data into the `callback_data` object.
    """
    user_id = str(callback.from_user.id)
    search_id = callback_data.search_id  # Safely get the ID
    
    # --- Delete from Database ---
    removed_search = await delete_search(user_id, search_id)
    # --- End Database Logic ---
    
    if removed_search:
        await callback.answer(f"נמחק: {removed_search['name']}")
        # Refresh the list by re-getting the data and editing the markup
        updated_searches = await get_searches(user_id)
        await callback.message.edit_reply_markup(
            reply_markup=search_list_keyboard(updated_searches)
        )
    else:
        await callback.answer("שגיאה: החיפוש לא נמצא.", show_alert=True)