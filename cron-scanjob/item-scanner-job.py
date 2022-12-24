import os
import logging
import requests

from connectors.db import Search

from yad2.yad2wrapper import get_search_item_ids

# initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BOT_TOKEN = os.environ['BOT_TOKEN']


def send_telegram_bot_message(bot_token, chat_id, message) -> None:
    """ send a regular message from a bot to user by his chat id """

    params = {
        "chat_id": chat_id,
        "text": message
    }
    requests.get(
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        params=params
    )


def send_telegram_bot_message_with_link(bot_token, chat_id, link, link_text) -> None:
    """ send a markdown message (can contains link as text) from a bot to user by his chat id """

    params = {
        "chat_id": chat_id,
        "text": f'[{link_text}]({link})',
        "parse_mode": "markdown",
    }
    requests.get(
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        params=params
    )


def scan_new_items() -> None:
    """Start the scanning job."""

    logger.info('starting scan new items job')

    for search in Search.scan():

        # get the current item ids of the search from previous scans
        current_item_ids_from_db = search.item_ids

        # get updated item ids from yad2
        # we want to avoid unnecessary calls to yad2 api (in order to not be blocked)
        # so if its the first scan for this search (item ids list in the db is empty) we need to scan all pages
        # else we can scan only the first page
        logger.info(f'request updated items of search id: {search.id}, name: {search.name}')

        # TODO: change only first page to be by last scan date
        updated_item_ids = get_search_item_ids(search_parameters=search.url,
                                               only_first_page=False if not current_item_ids_from_db else True)

        logger.info(
            f'successfully get {len(updated_item_ids)} updated_item_ids for for search: {search.id}, {search.name}')

        # extract only the new items that exists in the new retrieved item ids
        # and not exists in the search's item ids in the db
        new_updated_item_ids = list(set(updated_item_ids).difference(current_item_ids_from_db))

        if new_updated_item_ids and current_item_ids_from_db:
            logger.info(f'notify the user about new {len(new_updated_item_ids)} items')
            send_telegram_bot_message(BOT_TOKEN, search.chat_id, f'נצפו מודעות חדשות בחיפוש: {search.name}')

            for new_item_id in new_updated_item_ids:
                send_telegram_bot_message_with_link(BOT_TOKEN,
                                                    search.chat_id, f'https://www.yad2.co.il/item/{new_item_id}',
                                                    'לפתיחת המודעה')

        logger.info(f'update all new item ids in the db as item the user already notified')
        search.update(actions=[Search.item_ids.set(
            Search.item_ids.append(new_updated_item_ids)
        )])


def lambda_handler(event, context):
    try:
        scan_new_items()
    except Exception as error:
        logger.error(error)

# if __name__ == "__main__":
#     try:
#         scan_new_items()
#     except Exception as error:
#         logger.error(error)
