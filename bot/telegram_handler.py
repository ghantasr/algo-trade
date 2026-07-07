import json
import os
import urllib.parse
import urllib.request

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from utils.logger import logger

# File to persist known chat IDs so they survive restarts
CHAT_IDS_FILE = "data/known_chat_ids.json"


def _load_chat_ids() -> set:
    """Load known chat IDs from disk."""
    if not os.path.exists(CHAT_IDS_FILE):
        # Seed with the configured admin chat ID
        ids = {int(TELEGRAM_CHAT_ID)} if TELEGRAM_CHAT_ID else set()
        _save_chat_ids(ids)
        return ids
    try:
        with open(CHAT_IDS_FILE) as f:
            return set(json.load(f))
    except Exception:
        return {int(TELEGRAM_CHAT_ID)} if TELEGRAM_CHAT_ID else set()


def _save_chat_ids(ids: set):
    """Persist known chat IDs to disk."""
    os.makedirs(os.path.dirname(CHAT_IDS_FILE), exist_ok=True)
    with open(CHAT_IDS_FILE, "w") as f:
        json.dump(list(ids), f)


# In-memory + persisted set of all known chat IDs
_known_chat_ids: set = _load_chat_ids()


def _register_chat_id(chat_id: int):
    """Add a chat ID to the known list and persist."""
    if chat_id not in _known_chat_ids:
        _known_chat_ids.add(chat_id)
        _save_chat_ids(_known_chat_ids)
        logger.info("New chat ID registered: %s", chat_id)


def send_message_sync(text: str):
    """Send a Telegram message to ALL known users (safe to call from any thread)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in list(_known_chat_ids):
        try:
            payload = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }).encode()
            req = urllib.request.Request(url, data=payload, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                json.loads(resp.read())
            logger.info("Telegram message sent to %s: %s", chat_id, text[:80])
        except Exception as e:
            logger.warning("Failed to send message to chat %s: %s", chat_id, e)
    logger.info("Broadcast complete — sent to %d users", len(_known_chat_ids))


HELP_TEXT = (
    "👋 *NSE Intraday Advisory Bot*\n\n"
    "I analyse Indian stocks and tell you what to buy/sell.\n"
    "*You* place orders on your broker — I track your bucket.\n\n"
    "*Commands:*\n"
    "/run — Start market scanning\n"
    "/stop — Pause scanning\n"
    "/scan — Scan for buy opportunities now\n"
    "/bucket — Show your holdings & P&L\n"
    "/bought SYMBOL QTY PRICE — Confirm a buy\n"
    "/sold SYMBOL QTY PRICE — Confirm a sell\n"
    "/help — Show this message\n\n"
    "*Example workflow:*\n"
    "1. I send: BUY RELIANCE @ ₹2450\n"
    "2. You buy on Zerodha/Groww\n"
    "3. You reply: `/bought RELIANCE 4 2450`\n"
    "4. I track it and alert you when to sell"
)


class TelegramBot:
    """Telegram interface for human-in-the-loop trading."""

    def __init__(
        self,
        on_bought=None,
        on_sold=None,
        on_bucket=None,
        on_scan=None,
        on_start=None,
        on_stop=None,
    ):
        self.on_bought = on_bought
        self.on_sold = on_sold
        self.on_bucket = on_bucket
        self.on_scan = on_scan
        self.on_start = on_start
        self.on_stop = on_stop
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self._cmd_help))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("run", self._cmd_run))
        self.app.add_handler(CommandHandler("stop", self._cmd_stop))
        self.app.add_handler(CommandHandler("scan", self._cmd_scan))
        self.app.add_handler(CommandHandler("bucket", self._cmd_bucket))
        self.app.add_handler(CommandHandler("status", self._cmd_bucket))
        self.app.add_handler(CommandHandler("bought", self._cmd_bought))
        self.app.add_handler(CommandHandler("sold", self._cmd_sold))

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        _register_chat_id(update.effective_chat.id)
        await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")

    async def _cmd_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        _register_chat_id(update.effective_chat.id)
        if self.on_start:
            self.on_start()
        await update.message.reply_text("✅ Scanning started! I'll send buy/sell alerts during market hours.")

    async def _cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        _register_chat_id(update.effective_chat.id)
        if self.on_stop:
            self.on_stop()
        await update.message.reply_text("⏹ Scanning paused.")

    async def _cmd_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        _register_chat_id(update.effective_chat.id)
        if self.on_scan:
            msg = self.on_scan()
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("Scanner not ready yet.")

    async def _cmd_bucket(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        _register_chat_id(update.effective_chat.id)
        if self.on_bucket:
            msg = self.on_bucket()
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("Bucket not ready yet.")

    async def _cmd_bought(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        _register_chat_id(update.effective_chat.id)
        args = context.args
        if not args or len(args) < 3:
            await update.message.reply_text(
                "Usage: `/bought RELIANCE 4 2450.50`\n"
                "SYMBOL QTY PRICE",
                parse_mode="Markdown",
            )
            return
        try:
            symbol, qty, price = args[0], int(args[1]), float(args[2])
            if self.on_bought:
                msg = self.on_bought(symbol, qty, price)
                await update.message.reply_text(msg, parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("Invalid format. Example: `/bought RELIANCE 4 2450`", parse_mode="Markdown")

    async def _cmd_sold(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        _register_chat_id(update.effective_chat.id)
        args = context.args
        if not args or len(args) < 3:
            await update.message.reply_text(
                "Usage: `/sold RELIANCE 4 2580.00`\n"
                "SYMBOL QTY PRICE",
                parse_mode="Markdown",
            )
            return
        try:
            symbol, qty, price = args[0], int(args[1]), float(args[2])
            if self.on_sold:
                msg = self.on_sold(symbol, qty, price)
                await update.message.reply_text(msg, parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("Invalid format. Example: `/sold RELIANCE 4 2580`", parse_mode="Markdown")

    def run_polling(self):
        logger.info("Starting Telegram bot polling...")
        self.app.run_polling(drop_pending_updates=True)
