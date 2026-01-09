from aiogram import F, Router, types

from src.bot.keyboards.search_list import SearchCallback, search_list_keyboard
from src.bot.db import mock_db

router = Router()

@router.callback_query(F.data == "view_searches")
async def cb_view_searches(callback: types.CallbackQuery):
    """Shows all active searches with 'Delete' buttons."""
    user_id = str(callback.from_user.id)
    
    # --- Get from Database ---
    searches = await mock_db.get_searches(user_id)
    # --- End Database Logic ---
    
    if not searches:
        await callback.message.answer("You have no searches yet.")
    else:
        await callback.message.answer(
            "Your current searches:",
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
    removed_search = await mock_db.delete_search(user_id, search_id)
    # --- End Database Logic ---
    
    if removed_search:
        await callback.answer(f"Deleted: {removed_search['name']}")
        # Refresh the list by re-getting the data and editing the markup
        updated_searches = await mock_db.get_searches(user_id)
        await callback.message.edit_reply_markup(
            reply_markup=search_list_keyboard(updated_searches)
        )
    else:
        await callback.answer("Error: Search not found.", show_alert=True)