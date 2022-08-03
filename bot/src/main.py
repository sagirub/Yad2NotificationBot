# coding: utf-8

import logging

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
)

from start_menu import start, menu
from add_search import add_search, add_search_link, add_search_name
from search_list import search_list
from delete_search import delete_search
from error_handler import error_handler

from constants import *

from db import create_tables


logger = logging.getLogger(__name__)


# TODO: constatns to set as docker env variables
TOKEN = "1511431534:AAF81Ctf0tHiVkDeZDJuGaiI6h-XF3fAQLo"
LOG_FILE_PATH = 'bot.log'

def load_conversation_handler(application: Application) -> None:
    """Load conversation handler from files in a 'bot' directory"""

    selection_handlers = [
        CallbackQueryHandler(add_search, pattern='^' + str(ADD_SEARCH) + '$'),
        CallbackQueryHandler(search_list, pattern='^' + str(SEARCH_LIST) + '$'),
        CallbackQueryHandler(menu, pattern='^' + str(MENU) + '$'),
    ]

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_ACTION: selection_handlers,
            ADD_SEARCH_LINK: [MessageHandler(filters.TEXT, add_search_link,)],
            ADD_SEARCH_NAME: [MessageHandler(filters.TEXT, add_search_name)],
            DELETE_SEARCH: [MessageHandler(filters.Regex(DELETE_SEARCH_REGEX_PATTERN), delete_search)],
            MENU: [CallbackQueryHandler(menu, pattern='^' + str(MENU) + '$')],
        },
        fallbacks= [CallbackQueryHandler(menu)],
    )

    application.add_handler(conv_handler)

def main() -> None:
    """Run the bot."""

    # initalize the logger
    logging.basicConfig(filename=LOG_FILE_PATH,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    logger.info('build telegram bot application')
    application = Application.builder().token(TOKEN).build()
    load_conversation_handler(application)
    application.add_error_handler(error_handler)

    logger.info('create db tabels')
    create_tables()

    logger.info('start pulling bot')
    application.run_polling()
    logger.info('bot is active and wait for requests')


if __name__ == "__main__":
    main()
