import logging

from connectors.db import Search, Item

from yad2.yad2wrapper import get_search_item_ids

logger = logging.getLogger(__name__)

#TODO: parameter or env
BOT_TOKEN = "1511431534:AAF81Ctf0tHiVkDeZDJuGaiI6h-XF3fAQLo"
LOG_FILE_PATH = 'scanner-job.log'


def main() -> None:
    """Start the scanning job."""

    # initialize logger
    logging.basicConfig(filename=LOG_FILE_PATH,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    # get all searches from the db
    for search in Search.select():
        # we want only the last page items to avoid unnecessary calls to yad2 api
        there_are_exists_items = search.items.exists()
        current_item_ids_from_db = [item.item_id for item in search.items]
        # get updated current item ids from yad2
        updated_item_ids = get_search_item_ids(search_parameters=search.search_url,
                                               only_first_page= there_are_exists_items)

        # extract only the new items that exists in the new retrieved item ids
        # and not exists in the search's item ids in the db
        new_updated_item_ids = list(set(updated_item_ids).difference(current_item_ids_from_db))

        for new_item_id in new_updated_item_ids:
            # update the new item id to search items in the db
            Item.create(item_id=new_item_id, search_id=search.id)

            # get the item details
            message = f':נצפתה מודעה חדשה בחיפוש{search.search_name}'

            # notify the user about the new item with the details
            send_telegram_bot_message_with_link(message, f'https://www.yad2.co.il/item/{new_item_id}', 'למודעה')


def send_telegram_bot_message_with_link(message, link, link_text):
    params = {
        "chat_id": BOT_CHAT_ID,
        "text": f'{message}\n[{link_text}]({link})',
        "parse_mode": "markdown",
    }
    requests.get(
        "https://api.telegram.org/{}/sendMessage".format(BOT_TOKEN),
        params=params
    )


if __name__ == "__main__":
    main()
