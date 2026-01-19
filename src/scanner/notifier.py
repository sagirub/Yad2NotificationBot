"""
Telegram Notifier Module

This module handles sending notifications to users about new Yad2 listings
and admin notifications for scanner stats and alerts.
"""

import logging
import os
from typing import List, Optional

import requests

from src.config import settings
from src.yad2.parser import Yad2Item

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Sends Telegram notifications for new Yad2 items and admin stats.
    """
    
    def __init__(self, bot_token: str = None, admin_chat_id: str = None):
        """
        Initialize the notifier.
        
        Args:
            bot_token: Telegram bot token (uses env var if not provided)
            admin_chat_id: Admin chat ID for stats notifications (uses settings if not provided)
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN") or settings.TELEGRAM_BOT_TOKEN
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        self.admin_chat_id = admin_chat_id or os.environ.get("ADMIN_CHAT_ID") or settings.ADMIN_CHAT_ID
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"
        self.session = requests.Session()
    
    async def notify_new_items(
        self, 
        chat_id: str, 
        search_name: str, 
        items: List[Yad2Item]
    ) -> bool:
        """
        Send notification about new items to a user.
        
        Args:
            chat_id: Telegram chat ID
            search_name: Name of the search
            items: List of new Yad2Item objects
            
        Returns:
            True if notification was sent successfully
        """
        if not items:
            return True
        
        try:
            # Send header message
            header = f"🏠 *נמצאו {len(items)} מודעות חדשות!*\n\n"
            header += f"🔍 חיפוש: _{search_name}_"
            
            self._send_message(chat_id, header, parse_mode="Markdown")
            
            # Send each item
            for item in items:
                item_message = self._format_item_message(item)
                self._send_message(chat_id, item_message, parse_mode="Markdown")
            
            logger.info(f"Sent notification for {len(items)} items to chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification to {chat_id}: {e}")
            return False
    
    async def send_admin_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message to the admin chat.
        
        Args:
            text: Message text
            parse_mode: Parse mode (Markdown, HTML, etc.)
            
        Returns:
            True if sent successfully
        """
        if not self.admin_chat_id:
            logger.warning("Admin chat ID not configured, skipping admin notification")
            return False
        
        try:
            self._send_message(self.admin_chat_id, text, parse_mode=parse_mode)
            logger.info("Sent admin notification")
            return True
        except Exception as e:
            logger.error(f"Failed to send admin message: {e}")
            return False
    
    async def send_stats_summary(self, summary: str) -> bool:
        """
        Send a stats summary to the admin chat.
        
        Args:
            summary: Formatted stats summary string
            
        Returns:
            True if sent successfully
        """
        return await self.send_admin_message(summary)
    
    async def send_alert(self, alert: str) -> bool:
        """
        Send an alert to the admin chat.
        
        Args:
            alert: Alert message
            
        Returns:
            True if sent successfully
        """
        return await self.send_admin_message(alert)
    
    def _format_item_message(self, item: Yad2Item) -> str:
        """
        Format a single item as a Telegram message.
        
        Args:
            item: Yad2Item to format
            
        Returns:
            Formatted message string
        """
        lines = []
        
        # Title
        if item.title:
            lines.append(f"📌 *{self._escape_markdown(item.title)}*")
        
        # Price
        if item.price is not None:
            lines.append(f"💰 {self._escape_markdown(item.format_price())}")
        
        # Location
        if item.location:
            lines.append(f"📍 {self._escape_markdown(item.location)}")
        
        # Hand (for vehicles)
        if item.hand:
            lines.append(f"🔄 {self._escape_markdown(item.hand)}")
        
        # Link
        lines.append(f"\n[🔗 לצפייה במודעה]({item.link})")
        
        return "\n".join(lines)
    
    def _escape_markdown(self, text: str) -> str:
        """
        Escape special Markdown characters.
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text
        """
        if text is None:
            return ""
        text = str(text)
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def _send_message(
        self, 
        chat_id: str, 
        text: str, 
        parse_mode: str = None
    ) -> dict:
        """
        Send a message via Telegram API.
        
        Args:
            chat_id: Telegram chat ID
            text: Message text
            parse_mode: Parse mode (Markdown, HTML, etc.)
            
        Returns:
            API response
        """
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        
        if parse_mode:
            payload["parse_mode"] = parse_mode
        
        response = self.session.post(
            f"{self.api_base}/sendMessage",
            json=payload,
            timeout=30,
        )
        
        if not response.ok:
            logger.error(f"Telegram API error: {response.text}")
            response.raise_for_status()
        
        return response.json()
    
    def send_simple_message(self, chat_id: str, text: str) -> bool:
        """
        Send a simple text message.
        
        Args:
            chat_id: Telegram chat ID
            text: Message text
            
        Returns:
            True if sent successfully
        """
        try:
            self._send_message(chat_id, text)
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False