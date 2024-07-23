import sys
import requests
import logging
from urllib import parse
from datetime import datetime

from yad2constants import *

SEARCH_API_NETLOC = 'gw.yad2.co.il'
SEARCH_API_PATH_INITIAL = 'feed-search-legacy'
ITEM_API_BASE_URL = 'https://www.yad2.co.il/item/'
YAD2_NETLOC = 'www.yad2.co.il'
YAD2_DATETIME_STRING_FORMAT = '%Y-%m-%d %H:%M:%S'

# Init logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_search_item_ids(search_url: str,
                        commercial_items: bool = False,
                        max_pages: int = sys.maxsize,
                        min_addition_date: datetime = datetime.min) -> list:
    """
    Gets the current item ids appears in search by the search parameters

    Parameters
    ----------
    search_url : str
        The url of the search to find his current item ids
    commercial_items: bool
        Include commercial items from the search or only private
    max_pages: int, optional
        A int used to limit the number of search's pages requests
        (to avoid unnecessary requests of old items)
        the default value is integer max (because the function take the minimum
        between this value to the real number of pages)
    min_addition_date: datetime, optional
        A datetime used to get items that added only after specific date
        also help to avoid unnecessary request of old items
        because now can loop over pages until their update date is before
        the requested min added time
        this datetime must be in Asia/Jerusalem timezone!
        the default value is the minimum value of datetime

    Returns
    -------
    list
        a list of strings contains the current item ids of search
    """

    logger.info(f'get search items for search {search_url} '
                f'with params: max pages {max_pages}, min addition date {min_addition_date}')

    search_api_json_data = request_search_data(search_url)
    search_items_number = search_api_json_data['data']['feed']['total_items']
    search_pages_number = search_api_json_data['data']['feed']['total_pages']
    search_item_ids = []

    # if there are no items in the search result - return empty list
    if search_items_number == 0:
        return []

    # iterate over the search pages, extract all items from all pages
    for page in range(1, min(search_pages_number + 1, max_pages)):
        search_api_json_data = request_search_data(search_url, page)

        page_items = search_api_json_data['data']['feed']['feed_items']

        # filter all items (there is a lot of junk in the json, field has an id is real item)
        page_items = [item
                      for item in page_items
                      if 'id' in item and
                      datetime.strptime(item['date_added'], YAD2_DATETIME_STRING_FORMAT) > min_addition_date]

        # Filter commercial items
        if not commercial_items:
            page_items = [item for item in page_items if item['feed_source'] != 'commercial']

        # add all page item ids to the list to return
        search_item_ids.extend([item['id'] for item in page_items])

        # check minimum date limit
        # if the last update date of the last item in the page is before the minimum requested date
        # then all items in the next pages adding date *must* be before the minimum requested date and are not relevant
        if page_items:
            last_item_in_page = page_items[-1]

            if datetime.strptime(last_item_in_page['date'], YAD2_DATETIME_STRING_FORMAT) < min_addition_date:
                break

    # remove duplications of items
    search_item_ids = list(set(search_item_ids))

    logger.info(f'successfully get {len(search_item_ids)} items of the search {search_url}')

    return search_item_ids


def request_search_data(search_url: str, page: int = 1) -> dict:
    """
    Get regular search url, return the search api response json
    """
    search_api_url = build_api_search_url(search_url)

    try:
        response = requests.get(
            f'{search_api_url}&page={page}',
            headers={'Accept': 'application/json'},
        )
        response.raise_for_status()

        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f'There was an error while requesting {search_api_url}')
        logger.error(e, exc_info=True)
        raise e


def validate_search_url(search_url: str, access_check: bool = False) -> bool:
    """
    Check the search url is valid and can be tracked

    :param search_url: The search url to validate
    :param access_check: If true - do real request for the search to check for errors

    :return: True if the search url is valid or False otherwise
    """
    parsed_url = parse.urlparse(search_url)

    if parsed_url.netloc != YAD2_NETLOC:
        logger.error(f'Failed to validate the search url - {search_url} because invalid netloc')
        return False

    # basic request for the search with the api, to check if there are any errors because the url is invalid
    if access_check:
        try:
            request_search_data(search_url)
        except Exception as e:
            logger.error(f'Failed to validate the search url - {search_url} while trying to access the api')
            logger.error(e, exc_info=True)
            return False

    return True


def build_api_search_url(full_url: str) -> str:
    """
    Build api search url from the original full url
    Change the regular netloc of yad2 to the netloc of the api
    for example from "https://www.yad2.co.il/vehicles/cars?manufacturer=19" to
    "https://gw.yad2.co.il/feed-search-legacy/vehicles/cars?manufacturer=19"
    """
    parsed_url = parse.urlparse(full_url)
    # change 'www.yad2.co.il' to 'gw.yad2.co.il'
    parsed_url = parsed_url._replace(netloc=SEARCH_API_NETLOC)
    # add 'feed-search-legacy' to the beginning of the path
    parsed_url = parsed_url._replace(path=SEARCH_API_PATH_INITIAL + parsed_url.path)

    return parsed_url.geturl()


def fix_search_url(search_url: str) -> str:
    """
    Fix the search url if needed
    There are some common urls that contains search options that not acceptable in the search api
    for example - search url from map search - just need to delete the map from the url
    (more common search options that are not supported in the api can be added here)

    :param search_url: The search url to fix
    :return: The fixed url
    """
    # delete the map from url
    fixed_search_url = search_url.replace('/map', '')

    return fixed_search_url
