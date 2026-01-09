from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from src.bot.keyboards.main_menu import main_menu_keyboard

router = Router()

async def show_main_menu(message: types.Message, text: str):
    """Helper function to show the main menu."""
    await message.answer(text, reply_markup=main_menu_keyboard())

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Handles the /start command."""
    await show_main_menu(message, "Welcome! 🤖 Use the buttons below to manage your searches.")

@router.callback_query(F.data == "start_menu")
async def cb_start_menu(callback: types.CallbackQuery):
    """Handles the 'Back to menu' button."""
    await callback.answer()
    await show_main_menu(callback.message, "Welcome! 🤖 Use the buttons below to manage your searches.")

@router.message(Command("cancel"))
@router.callback_query(F.data == "cancel")
async def cmd_cancel(event: types.Update, state: FSMContext):
    """A global cancel command for any FSM state."""
    await state.clear()
    message = event.message if isinstance(event, types.Message) else event.callback_query.message
    await show_main_menu(message, "Operation cancelled. What's next?")
    if isinstance(event, types.CallbackQuery):
        await event.answer()