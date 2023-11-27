import sys
import logging
import requests
from datetime import datetime

from yad2utils import *

# Init logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_search_item_ids(search_parameters: str, max_pages: int = sys.maxsize,
                        min_addition_date: datetime = datetime.min) -> list:
    """
    Gets the current item ids appears in search by the search parameters

    Parameters
    ----------
    search_parameters : str
        The url parameters of the search to find his current item ids
    max_pages: int, optional
        A int used to limit the number of search's pages requests
        (to avoid unnecessary requests of old items)
        default value is integer max
    min_addition_date: datetime, optional
        A datetime used to get items that added only after specific time
        also help to avoid unnecessary request of old items
        because now can loop over pages until their update date is before
        the requested min added time
        this datetime must be in Asia/Jerusalem timezone!
        default value is the minimum value of datetime

    Returns
    -------
    list
        a list of strings contains the current item ids of search
    """

    logger.info(f'start get search items for search {search_parameters}')
    search_api_url = SEARCH_API_BASE_URL + search_parameters.strip("/")

    try:
        response = requests.get(
            search_api_url,
            headers={'Accept': 'application/json'},
        )
        response.raise_for_status()
    except Exception as e:
        logger.error(f'there was an error while requesting {search_api_url}\n{e}')
        raise e

    response_feed_items_json = response.json()['data']['feed']

    # if there are no items in the search result - return empty list
    if response_feed_items_json['total_items'] == 0:
        return []

    total_pages = response_feed_items_json['total_pages']
    search_item_ids = []

    # iterate over the search page, extract all item ids from every page
    for page_id in range(1, min(total_pages + 1, max_pages)):
        try:
            logger.info(f'request page {page_id}')
            response = requests.get(
                f'{search_api_url}&page={page_id}',
                headers={'Accept': 'application/json'},
            )
        except Exception as e:
            logger.error(f'there was an error while requesting {f"{search_api_url}&page={page_id}"}\n{e}')
            raise e

        response_feed_items_json = response.json()['data']['feed']['feed_items']

        page_item_ids = [item['link_token']
                         for item in response_feed_items_json
                         if 'link_token' in item and
                         datetime.strptime(item['date_added'], YAD2_DATETIME_STRING_FORMAT) > min_addition_date]
        search_item_ids.extend(page_item_ids)

        # Check minimum date limit
        # if the last item update date is before the minimum requested date
        # then all items in the next pages adding date *must* be before the minimum requested date
        # in the end of the loop to avoid another request
        # the second item from the end because the last item in the json is not really item from the search (yad2?!)
        last_item_in_page = response_feed_items_json[-2]
        if ('date' in last_item_in_page and
                datetime.strptime(last_item_in_page['date'], YAD2_DATETIME_STRING_FORMAT) < min_addition_date):
            break

    logger.info(f'successfully get search items, {len(search_item_ids)} items retrieved')

    return search_item_ids
