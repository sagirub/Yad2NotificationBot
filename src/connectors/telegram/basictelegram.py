import os
import requests

BOT_TOKEN = os.environ['BOT_TOKEN']


def send_telegram_bot_message(chat_id: int, message: str) -> None:
    """ send a regular message from a bot to user by his chat id """

    params = {
        "chat_id": chat_id,
        "text": message
    }
    requests.get(
        f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
        params=params
    )


def send_telegram_bot_message_with_link(chat_id: int, link: str, link_text: str) -> None:
    """ send a markdown message (can contain link as text) from a bot to user by his chat id """

    params = {
        "chat_id": chat_id,
        "text": f'[{link_text}]({link})',
        "parse_mode": "markdown",
    }
    requests.get(
        f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
        params=params
    )