#!/usr/bin/env python3
"""
Script to set the Telegram webhook URL after deployment.

Usage:
    python scripts/set_webhook.py

Environment variables:
    TELEGRAM_BOT_TOKEN: Your bot token from @BotFather
    WEBHOOK_URL: The URL to set as webhook (from serverless deploy output)
"""
import os
import sys
import requests


def set_webhook():
    """Set the Telegram webhook URL."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    webhook_url = os.environ.get("WEBHOOK_URL")
    
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)
    
    if not webhook_url:
        print("❌ Error: WEBHOOK_URL environment variable not set")
        sys.exit(1)
    
    # Telegram API endpoint
    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    
    # Set webhook
    response = requests.post(api_url, json={
        "url": webhook_url,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": False
    })
    
    result = response.json()
    
    if result.get("ok"):
        print(f"✅ Webhook set successfully!")
        print(f"   URL: {webhook_url}")
    else:
        print(f"❌ Failed to set webhook: {result.get('description', 'Unknown error')}")
        sys.exit(1)


def get_webhook_info():
    """Get current webhook info."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)
    
    api_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    response = requests.get(api_url)
    result = response.json()
    
    if result.get("ok"):
        info = result.get("result", {})
        print("📡 Current Webhook Info:")
        print(f"   URL: {info.get('url', 'Not set')}")
        print(f"   Pending updates: {info.get('pending_update_count', 0)}")
        if info.get("last_error_message"):
            print(f"   Last error: {info.get('last_error_message')}")
    else:
        print(f"❌ Failed to get webhook info: {result.get('description')}")


def delete_webhook():
    """Delete the current webhook (for switching to polling mode)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)
    
    api_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    response = requests.post(api_url, json={"drop_pending_updates": False})
    result = response.json()
    
    if result.get("ok"):
        print("✅ Webhook deleted successfully!")
        print("   Bot is now ready for polling mode.")
    else:
        print(f"❌ Failed to delete webhook: {result.get('description')}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage Telegram webhook")
    parser.add_argument("action", nargs="?", default="set", 
                       choices=["set", "info", "delete"],
                       help="Action to perform (default: set)")
    
    args = parser.parse_args()
    
    if args.action == "set":
        set_webhook()
    elif args.action == "info":
        get_webhook_info()
    elif args.action == "delete":
        delete_webhook()