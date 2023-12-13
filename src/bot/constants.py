# encoding: utf-8

import os
from telegram.ext import ConversationHandler

# Environment variables
DEBUG = os.getenv('DEBUG', False) == 'True'
# the prod bot using webhook, the dev bot using pooling
BOT_TOKEN = os.environ['BOT_TOKEN']


START, MENU, MENU_SELECTING_ACTION, ADD_SEARCH, ADD_SEARCH_LINK, ADD_SEARCH_NAME, DELETE_SEARCH, SEARCH_LIST = range(8)

# Shortcut for ConversationHandler.END
END = ConversationHandler.END

# TODO: WHATS IS THIS??
DEVELOPER_CHAT_ID = 12345678

# Messages text

START_MESSAGE = (
        'ברוכים הבאים לבוט התראות ל-יד2.'
        '\n\n'
        'אני אעזור לך לעקוב אחרי חיפושים ביד2 ולקבל התראות על מודעות חדשות'
        '\n\n'
        'זה מה שאני מסוגל לעשות:'
        '\n\n'
        'קבלת התראות על חיפושים 🔎'
        '\n\n'
        'בא נתחיל! 👇'
)

ADD_SEARCH_MESSAGE = (
        'העתק לכאן את שורת הכתובת של החיפוש, לדוגמא:'
        '\n\n'
        'https://www.yad2.co.il/vehicles/cars?year=2015--1&price=5000-30000&km=10000-200000&gearBox=0'
)

ADD_SEARCH_LINK_MESSAGE = (
        'מעולה! עכשיו תן שם לחיפוש שלך, לדוגמא:'
        '\n\n'
        'כל הרכבים הידניים מעל שנת 2015 עד 30,000 שקל'
)

ADD_SEARCH_LINK_ERROR_MESSAGE = (
        'נראה שהלינק שהזנת לא תקין, נסה שוב, לינק לדוגמא:'
        '\n\n'
        'https://www.yad2.co.il/vehicles/cars?price=5000-30000'
)

ADD_SEARCH_SUCCESS_END_MESSAGE = (
        'החיפוש נשמר בהצלחה, מעכשיו תקבל התראה על כל מודעה חדשה!'
        '\n\n'
        'תוכל לעקוב אחרי רשימת החיפושים שלך ולמחוק חיפושים קיימים דרך \"רשימת החיפושים שלי\"'
)

ADD_SEARCH_FAIL_END_MESSAGE = (
        'הוספת החיפוש נכשלה, אנא נסה שנית!'
        '\n\n'
        'תוכל לעקוב אחרי רשימת החיפושים שלך ולמחוק חיפושים קיימים דרך \"רשימת החיפושים שלי\"'
)


DELETE_SEARCH_SUCCESS_END_MESSAGE = (
        'החיפוש נמחק בהצלחה, מעכשיו כבר לא תקבל התראה על כל מודעה חדשה!'
        '\n\n'
        'תוכל לעקוב אחרי רשימת החיפושים שלך ולמחוק חיפושים קיימים דרך \"רשימת החיפושים שלי\"'
)

DELETE_SEARCH_FAIL_END_MESSAGE = (
        'מחיקת החיפוש נכשלה, ייתכן שהחיפוש לא קיים, אנא נסה שנית'
        '\n\n'
        'תוכל לעקוב אחרי רשימת החיפושים שלך ולמחוק חיפושים קיימים דרך \"רשימת החיפושים שלי\"'
)

SEARCH_LIST_TEXT = (
        'רשימת החיפושים שלך:'
        '\n\n'
)

EMPTY_SEARCH_LIST_TEXT = (
        'רשימת החיפושים שלך ריקה'
        '\n\n'
        'לחץ על הוספת חיפוש חדש להוספת חיפוש חדש'
)

MENU_BUTTON_TEXT = 'תפריט'

MENU_INITIAL_TEXT = 'בחר את הפעולה הרצויה'

MENU_ADD_SEARCH_BUTTON_TEXT = 'הוספת חיפוש חדש 🔎'

VALIDATING_SEARCH_LINK_AWAIT_MESSAGE = 'מוודא שהלינק תקין..'

MENU_SEARCH_LIST_BUTTON_TEXT = 'החיפושים שלי 📃'

# Regex patterns
DELETE_SEARCH_REGEX_PATTERN = 'ds_(.*)'