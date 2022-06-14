# encoding: utf-8

from telegram.ext import ConversationHandler

START, MENU, SELECTING_ACTION, ADD_SEARCH, ADD_SEARCH_LINK, ADD_SEARCH_NAME, DELETE_SEARCH, SEARCH_LIST = range(8)

# Shortcut for ConversationHandler.END
END = ConversationHandler.END

#TODO: CREATE GROUP ONLY WITH ME
DEVELOPER_CHAT_ID = 123456789

# Messages text

START_MESSAGE = (
        'ברוכים הבאים לבוט התראות ל-יד2.'
        '\n\n'
        'אני יעזור לך לעקוב אחרי חיפושים ביד2 ולקבל התראות על מודעות חדשות'
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
        'https://www.yad2.co.il/vehicles/private-cars?price=5000-30000'
)

ADD_SEARCH_LINK_MESSAGE = (
        'מעולה! עכשיו תן שם לחיפוש שלך, לדוגמא:'
        '\n\n'
        'טורבו דיזל ידנית עד 100,000 קמ'
)

ADD_SEARCH_LINK_ERROR_MESSAGE = (
        'נראה שהלינק שהזנת לא תקין, נסה שוב, לינק לדוגמא:'
        '\n\n'
        'https://www.yad2.co.il/vehicles/private-cars?price=5000-30000'
)

ADD_SEARCH_END_MESSAGE = (
        'החיפוש נשמר בהצלחה, מעכשיו תקבל התראה על כל מודעה חדשה!'
        '\n\n'
        'תוכל לעקוב אחרי רשימת החיפושים שלך ולמחוק חיפושים קיימים דרך \"רשימת החיפושים שלי\"'
)


DELETE_SEARCH_END_MESSAGE = (
        'החיפוש נמחק בהצלחה, מעכשיו כבר לא תקבל התראה על כל מודעה חדשה!'
        '\n\n'
        'תוכל לעקוב אחרי רשימת החיפושים שלך ולמחוק חיפושים קיימים דרך \"רשימת החיפושים שלי\"'
)

SEARCH_LIST_TEXT = (
        'רשימת החיפושים שלך:'
        '\n\n'
)

MENU_BUTTON_TEXT = 'תפריט'

MENU_INITIAL_TEXT = 'בחר את הפעולה הרצויה'

MENU_ADD_SEARCH_BUTTON_TEXT = 'הוספת חיפוש חדש 🔎'

MENU_SEARCH_LIST_BUTTON_TEXT = 'רשימת החיפושים שלי 📃'

# Yad2 url constans
YAD2_VALID_NETLOC = 'www.yad2.co.il'


# Regex patterns
DELETE_SEARCH_REGEX_PATTERN = 'ds_(.*)'