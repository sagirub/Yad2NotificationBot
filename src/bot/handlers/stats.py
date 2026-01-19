"""
Stats Command Handler

This module provides the /stats command for viewing scanner statistics.
Only accessible by the admin (ADMIN_CHAT_ID).
"""

import logging
from aiogram import Router, types
from aiogram.filters import Command

from src.config import settings
from src.bot.db.dynamodb import get_stats_summary, get_latest_stats
from src.scanner.stats import format_summary_message

logger = logging.getLogger(__name__)

router = Router()


def is_admin(user_id: int) -> bool:
    """Check if user is the admin."""
    if not settings.ADMIN_CHAT_ID:
        return False
    return str(user_id) == str(settings.ADMIN_CHAT_ID)


@router.message(Command("stats"))
async def stats_command(message: types.Message):
    """
    Handle /stats command.
    
    Usage:
        /stats - Today's summary
        /stats today - Today's detailed stats
        /stats week - Last 7 days summary
        /stats recent - Last 10 scan runs
    """
    user_id = message.from_user.id
    
    # Check if user is admin
    if not is_admin(user_id):
        await message.answer(
            "⛔ This command is only available to administrators."
        )
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if message.text else []
    period = args[0].lower() if args else "today"
    
    try:
        if period == "today":
            summary = await get_stats_summary(days=1)
            response = format_summary_message(summary, "Today's Stats")
        elif period == "week":
            summary = await get_stats_summary(days=7)
            response = format_summary_message(summary, "Weekly Stats")
        elif period == "recent":
            recent = await get_latest_stats(limit=10)
            response = format_recent_stats(recent)
        else:
            # Default to today
            summary = await get_stats_summary(days=1)
            response = format_summary_message(summary, "Today's Stats")
        
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}", exc_info=True)
        await message.answer(
            "❌ Error fetching stats. Please try again later."
        )


def format_recent_stats(stats_list: list) -> str:
    """
    Format recent stats as a Telegram message.
    
    Args:
        stats_list: List of recent stats records
        
    Returns:
        Formatted string for Telegram
    """
    if not stats_list:
        return "📊 No recent stats available"
    
    lines = [
        "📊 *Recent Scanner Runs*",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]
    
    for stat in stats_list:
        timestamp = stat.get("timestamp", "Unknown")
        # Parse timestamp to show just time
        if "T" in timestamp:
            time_part = timestamp.split("T")[1][:5]
            date_part = timestamp.split("T")[0][5:]  # MM-DD
            display_time = f"{date_part} {time_part}"
        else:
            display_time = timestamp[:16]
        
        searches = stat.get("searches_scanned", 0)
        items = stat.get("items_found", 0)
        success = stat.get("requests_success", 0)
        blocked = stat.get("requests_blocked", 0)
        failed = stat.get("requests_failed", 0)
        
        # Status emoji based on results
        if blocked > 0:
            status = "🚫"
        elif failed > 0:
            status = "⚠️"
        elif items > 0:
            status = "🆕"
        else:
            status = "✅"
        
        lines.append(
            f"{status} `{display_time}` | 📊{searches} | 🆕{items} | ✅{success}/🚫{blocked}/❌{failed}"
        )
    
    lines.append("")
    lines.append("_Legend: 📊=searches, 🆕=new items, ✅=success, 🚫=blocked, ❌=failed_")
    
    return "\n".join(lines)


@router.message(Command("help_stats"))
async def help_stats_command(message: types.Message):
    """Show help for stats commands."""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer(
            "⛔ This command is only available to administrators."
        )
        return
    
    help_text = """
📊 *Stats Commands*

/stats - Today's summary
/stats today - Today's detailed stats
/stats week - Last 7 days summary
/stats recent - Last 10 scan runs

*Metrics Explained:*
• 📊 Searches Scanned - Number of user searches processed
• 🆕 Items Found - New listings detected
• 📨 Notifications - Messages sent to users
• ✅ Success Rate - Successful Yad2 requests
• 🚫 Block Rate - Requests blocked by captcha
• ❌ Error Rate - Failed requests

*Detection Methods:*
• 📷 Image URL - Timestamp extracted from image filename
• 🔗 API Call - Fallback to item detail API
"""
    
    await message.answer(help_text, parse_mode="Markdown")