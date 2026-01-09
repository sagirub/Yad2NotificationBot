from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from src.bot.states import AddSearch
from src.bot.keyboards.main_menu import main_menu_keyboard
from src.bot.db import mock_db

router = Router()

def is_valid_link(link: str) -> bool:
    """Placeholder for your link validation logic."""
    # TODO: Add real regex for yad2.co.il or other sites
    return link.startswith("http://") or link.startswith("https://")

@router.callback_query(F.data == "add_search")
async def cb_add_search(callback: types.CallbackQuery, state: FSMContext):
    """Entry point for the 'add search' conversation."""
    await callback.message.answer(
        "Please send me the link you want to track.\n"
        "Send /cancel to stop."
    )
    await state.set_state(AddSearch.waiting_for_link)
    await callback.answer()

@router.message(AddSearch.waiting_for_link, F.text)
async def handle_link(message: types.Message, state: FSMContext):
    """Handles the 'waiting_for_link' state."""
    link = message.text.strip()
    if not is_valid_link(link):
        await message.answer(
            "That doesn't look like a valid link. Please send a full URL.\n"
            "Send /cancel to stop."
        )
        return  # Stay in the same state

    # Save the link in the FSM's in-memory storage
    await state.update_data(link=link)
    
    await message.answer(
        "✅ Link received. Now, what do you want to name this search?\n"
        "Send /cancel to stop."
    )
    await state.set_state(AddSearch.waiting_for_name)

@router.message(AddSearch.waiting_for_name, F.text)
async def handle_name(message: types.Message, state: FSMContext):
    """Handles the 'waiting_for_name' state."""
    user_id = str(message.from_user.id)
    name = message.text.strip()
    
    # Retrieve the link we saved in the previous step
    data = await state.get_data()
    link = data.get("link")

    if not link:
        await message.answer("Something went wrong. Please start over with /add.")
        await state.clear()
        return

    # --- Add to Database ---
    await mock_db.add_search(user_id=user_id, name=name, link=link)
    # --- End Database Logic ---
    
    await state.clear()
    await message.answer(
        f"✅ Added new search: {name}",
        reply_markup=main_menu_keyboard()
    )