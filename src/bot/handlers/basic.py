# src/bot/handlers/basic.py
from aiogram import Router, types
from aiogram.filters import Command
from .list_searches import search_menu_keyboard

router = Router()

@router.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Welcome! 🤖",
        reply_markup=search_menu_keyboard()
    )
