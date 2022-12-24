# coding: utf-8

import logging
import asyncio
import json

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    PicklePersistence,
    filters,
)
from telegram import Update

from bot.start_menu import start, menu
from bot.add_search import add_search, add_search_link, add_search_name
from bot.search_list import search_list
from bot.delete_search import delete_search
from bot.error_handler import error_handler

from bot.constants import *

from connectors.db import create_table

logger = logging.getLogger(__name__)

# TODO: implement basepersistence class with dynamodb
# TODO: update in build and load_conversation_handler
#PERSISTENCE_FILE_PATH = 'bot_persistence_pickle_data'
#persistence = PicklePersistence(filepath=PERSISTENCE_FILE_PATH)

# initialize logger
logging.getLogger().setLevel(logging.INFO)

logging.info(f'starting bot in {"production" if PROD else "dev"} mode')
application = Application.builder().token(PROD_TELEGRAM_BOT_TOKEN if PROD else DEV_TELEGRAM_BOT_TOKEN).build()#.persistence(persistence).build()

create_table()


def load_conversation_handler(application: Application) -> None:
    """Load all conversation handlers"""

    logging.info('loading conversation handler')
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
        fallbacks=[CallbackQueryHandler(menu)],
        name='my_conversation',
        #persistent=True,
    )
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)


def debug_main() -> None:
    """ debug main - run the bot using polling """

    try:
        load_conversation_handler(application)
        logger.info('start polling...')
        application.run_polling()
    except Exception as error:
        logger.error(error)


async def main(event, context) -> None:
    """prod main - Run the bot using webhook with lambda"""

    load_conversation_handler(application)

    try:
        await application.initialize()
        await application.process_update(
            Update.de_json(json.loads(event["body"]), application.bot)
        )

        return {
            'statusCode': 200,
            'body': 'Success'
        }

    except Exception as error:
        logger.error(error)

        return {
            'statusCode': 500,
            'body': 'Failure'
        }


def lambda_handler(event, context):
    return asyncio.get_event_loop().run_until_complete(main(event, context))


if __name__ == "__main__":
    if not PROD:
        debug_main()
