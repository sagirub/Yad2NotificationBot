# encoding: utf-8

import logging

# Telegram API framework core imports
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CallbackContext

# Bot constatns
from constants import *

# Init logger
logger = logging.getLogger(__name__)


async def delete_search(update: Update, context: CallbackContext.DEFAULT_TYPE) -> int:
    """Delete search by id"""
    search_id = update.message.text.replace("/ds_", "")

    #TODO: REMOVE SEARCH ROW FROM THE DB
    logger.info(f'search was successfully added: user_id:{update.message.from_user.id}, \
                  user_name: {update.message.forward_sender_name}, \
                  search_name: {search_id}')


    buttons = [
        [
            InlineKeyboardButton(MENU_BUTTON_TEXT, callback_data=str(MENU))
        ]
    ]

    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(text=DELETE_SEARCH_END_MESSAGE, reply_markup=keyboard)

    return MENU