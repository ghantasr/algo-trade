#!/usr/bin/env python3
"""
Quick test: verifies your Telegram bot token and chat ID work.
Run this BEFORE starting the full app.

Usage:
    python scripts/test_telegram.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.telegram_handler import send_message_sync
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def main():
    print("Testing Telegram connection...")
    print(f"  Bot token: {TELEGRAM_BOT_TOKEN[:10]}...")
    print(f"  Chat ID:   {TELEGRAM_CHAT_ID}")

    send_message_sync("✅ Telegram connection works! Your algo-trade bot is ready to set up.")

    print("\nSuccess! Check your Telegram — you should see a test message.")


if __name__ == "__main__":
    main()
