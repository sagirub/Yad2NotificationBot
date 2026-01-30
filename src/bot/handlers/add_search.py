import logging
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.bot.states import AddSearch
from src.bot.keyboards.main_menu import main_menu_keyboard
from src.bot.db import add_search as db_add_search, get_total_search_count
from src.config import settings

logger = logging.getLogger(__name__)

router = Router()


def is_valid_link(link: str) -> bool:
    """Validate that the link is a valid Yad2 URL."""
    if not (link.startswith("http://") or link.startswith("https://")):
        return False
    # Check if it's a yad2.co.il URL
    return "yad2.co.il" in link


def get_initial_search_info(link: str) -> tuple[int | None, bool | None]:
    """
    Fetch initial search info to determine search size.
    
    Args:
        link: The Yad2 search URL
        
    Returns:
        Tuple of (total_items, is_small_search) or (None, None) if fetch fails
    """
    try:
        from src.yad2.parser import Yad2Parser
        
        parser = Yad2Parser(request_delay=0)  # No delay for single request
        result = parser.get_search_result(link)
        
        total_items = result.total_results
        if total_items is not None:
            is_small = total_items <= settings.SMALL_SEARCH_THRESHOLD
            logger.info(f"Search has {total_items} items, is_small={is_small}")
            return total_items, is_small
        else:
            # Fallback: estimate from items fetched
            items_count = len(result.items)
            is_small = items_count <= settings.SMALL_SEARCH_THRESHOLD
            logger.info(f"Could not get total_results, using items count: {items_count}, is_small={is_small}")
            return items_count, is_small
            
    except Exception as e:
        logger.warning(f"Failed to fetch initial search info: {e}")
        return None, None


def commercial_filter_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for commercial filter selection."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ כן, רק פרטיים", callback_data="filter_commercial_yes"),
            InlineKeyboardButton(text="❌ לא, הכל", callback_data="filter_commercial_no"),
        ]
    ])


@router.callback_query(F.data == "add_search")
async def cb_add_search(callback: types.CallbackQuery, state: FSMContext):
    """Entry point for the 'add search' conversation."""
    # Check if we've reached the total search limit
    total_searches = await get_total_search_count()
    if total_searches >= settings.MAX_SEARCHES_TOTAL:
        await callback.message.answer(
            f"⚠️ מצטערים, הגענו למגבלה המקסימלית של {settings.MAX_SEARCHES_TOTAL} חיפושים.\n"
            "נסו שוב מאוחר יותר או פנו למנהל.",
            reply_markup=main_menu_keyboard()
        )
        await callback.answer()
        return
    
    await callback.message.answer(
        "שלחו לי את הלינק שתרצו לעקוב אחריו.\n"
        "שלחו /cancel לביטול."
    )
    await state.set_state(AddSearch.waiting_for_link)
    await callback.answer()


@router.message(AddSearch.waiting_for_link, F.text)
async def handle_link(message: types.Message, state: FSMContext):
    """Handles the 'waiting_for_link' state."""
    link = message.text.strip()
    if not is_valid_link(link):
        await message.answer(
            "זה לא נראה כמו לינק תקין של יד2. שלחו כתובת מלאה מ-yad2.co.il.\n"
            "שלחו /cancel לביטול."
        )
        return  # Stay in the same state

    # Save the link in the FSM's in-memory storage
    await state.update_data(link=link)
    
    # Ask about commercial filter
    await message.answer(
        "✅ הלינק התקבל.\n\n"
        "האם לסנן מודעות של סוחרים ומתווכים?\n"
        "(תקבלו התראות רק על מודעות פרטיות)",
        reply_markup=commercial_filter_keyboard()
    )
    await state.set_state(AddSearch.waiting_for_commercial_filter)


@router.callback_query(AddSearch.waiting_for_commercial_filter, F.data.startswith("filter_commercial_"))
async def handle_commercial_filter(callback: types.CallbackQuery, state: FSMContext):
    """Handles the commercial filter selection."""
    exclude_commercial = callback.data == "filter_commercial_yes"
    
    # Save the preference
    await state.update_data(exclude_commercial=exclude_commercial)
    
    filter_text = "כן, רק פרטיים" if exclude_commercial else "לא, הכל"
    await callback.message.edit_text(
        f"✅ סינון סוחרים: {filter_text}\n\n"
        "איך תרצו לקרוא לחיפוש הזה?\n"
        "שלחו /cancel לביטול."
    )
    await state.set_state(AddSearch.waiting_for_name)
    await callback.answer()


@router.message(AddSearch.waiting_for_name, F.text)
async def handle_name(message: types.Message, state: FSMContext):
    """Handles the 'waiting_for_name' state."""
    user_id = str(message.from_user.id)
    name = message.text.strip()
    
    # Retrieve the data we saved in previous steps
    data = await state.get_data()
    link = data.get("link")
    exclude_commercial = data.get("exclude_commercial", False)

    if not link:
        await message.answer("משהו השתבש. התחילו מחדש עם /add.")
        await state.clear()
        return

    # Notify user we're processing
    processing_msg = await message.answer("⏳ מוסיף חיפוש ומנתח...")
    
    # Fetch initial search info to determine search size
    total_items, is_small_search = get_initial_search_info(link)
    
    # --- Add to Database ---
    await db_add_search(
        user_id=user_id,
        name=name,
        link=link,
        total_items=total_items,
        is_small_search=is_small_search,
        exclude_commercial=exclude_commercial,
    )
    # --- End Database Logic ---
    
    await state.clear()
    
    # Build response message
    size_info = ""
    if total_items is not None:
        size_type = "קטן" if is_small_search else "גדול"
        size_info = f"\n📊 גודל חיפוש: {total_items} פריטים (חיפוש {size_type})"
    
    filter_info = "\n🚫 סינון סוחרים: פעיל" if exclude_commercial else ""
    
    await processing_msg.edit_text(
        f"✅ נוסף חיפוש חדש: {name}{size_info}{filter_info}",
        reply_markup=main_menu_keyboard()
    )