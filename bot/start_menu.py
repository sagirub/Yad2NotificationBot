# encoding: utf-8

import logging

# Telegram API framework core imports
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CallbackContext

# Bot constants
from bot.constants import *

# Init logger
logger = logging.getLogger(__name__)


async def start(update: Update, context: CallbackContext.DEFAULT_TYPE) -> int:
    """Send a message when the command /start is issued."""
    
    logger.info(f'new user start chat with the bot: user_id:{update.message.from_user.id}, name: {update.message.chat.first_name}')

    await update.message.reply_text(text=START_MESSAGE)

    return await menu(update, context)


async def menu(update: Update, context: CallbackContext.DEFAULT_TYPE) -> int:
    """serve the menu to the user"""

    buttons = [
        [
            InlineKeyboardButton(MENU_ADD_SEARCH_BUTTON_TEXT, callback_data=str(ADD_SEARCH)),
            InlineKeyboardButton(MENU_SEARCH_LIST_BUTTON_TEXT, callback_data=str(SEARCH_LIST)),
        ]
    ]

    keyboard = InlineKeyboardMarkup(buttons)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=MENU_INITIAL_TEXT,
        reply_markup=keyboard
    )

    return SELECTING_ACTION
