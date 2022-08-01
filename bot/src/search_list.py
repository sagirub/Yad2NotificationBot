# encoding: utf-8

import logging

# Telegram API framework core imports
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CallbackContext

# Bot constatns
from constants import *

#Init logger
logger = logging.getLogger(__name__)


async def search_list(update: Update, context: CallbackContext.DEFAULT_TYPE) -> int:
    """Send a message when the command /searchlist is issued."""
    
    # TODO: get list of searches by the user, contains - search id with search name,
    # link to the search and link to command to delete the search
    # USE SEARCH_LIST_TEXT
    
    # USED TEMP MESSAGE ONLY FOR TESTS
    test_text_example = (
        'רשימת החיפושים שלך:'
        '\n\n'
        'טורבו דיזל ידנית עד 100,000 קמ'
        '\n'
        'לחץ למחיקת החיפוש: '
        '/ds\_1234'
        '\n\n'
        'טורבו דיזל ידנית עד 150,000 קמ'
        '\n'
        'לחץ למחיקת החיפוש: '
        '/ds\_1235'
    )

    buttons = [
        [
            InlineKeyboardButton(MENU_BUTTON_TEXT, callback_data=str(MENU))
        ]
    ]

    keyboard = InlineKeyboardMarkup(buttons)

    await update.callback_query.answer()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=test_text_example,
        parse_mode='Markdown',
        reply_markup = keyboard
    )

    return DELETE_SEARCH