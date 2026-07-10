import os
from dotenv import load_dotenv

load_dotenv()


def get_env(key: str, default: str = "") -> str:
    value = os.getenv(key, default)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = get_env("TELEGRAM_CHAT_ID")

# Indian NSE settings
MARKET = "NSE"
INTERVAL = os.getenv("INTERVAL", "5m")
SHORT_MA = int(os.getenv("SHORT_MA", "9"))
LONG_MA = int(os.getenv("LONG_MA", "21"))

# How often to scan & check positions (seconds). 120 = every 2 minutes
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "120"))

# ₹ amount to invest per stock suggestion
INVESTMENT_PER_TRADE = float(os.getenv("INVESTMENT_PER_TRADE", "10000"))

# Profit target range (after broker fees)
TARGET_PROFIT_PCT = float(os.getenv("TARGET_PROFIT_PCT", "5"))
MAX_PROFIT_PCT = float(os.getenv("MAX_PROFIT_PCT", "10"))

# Sell if loss exceeds this % (after fees)
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "2"))

# Exit all positions this many minutes before NSE close (3:30 PM IST)
EXIT_MINUTES_BEFORE_CLOSE = int(os.getenv("EXIT_MINUTES_BEFORE_CLOSE", "60"))

# Max stocks to hold at once
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "3"))

# Max buy suggestions per scan
MAX_BUY_SUGGESTIONS = int(os.getenv("MAX_BUY_SUGGESTIONS", "2"))

# Minimum % gain today before suggesting a buy (must already be moving up)
MIN_GAIN_PCT = float(os.getenv("MIN_GAIN_PCT", "0.5"))

# Pre-market analysis settings
PREDICTION_LOOKBACK_DAYS = int(os.getenv("PREDICTION_LOOKBACK_DAYS", "20"))
PREMARKET_ONLY = os.getenv("PREMARKET_ONLY", "false").lower() == "true"

# Auto-start scanning on boot (for headless/GitHub Actions mode)
AUTO_START = os.getenv("AUTO_START", "false").lower() == "true"

# File to store today's discovered stocks
CANDIDATES_FILE = os.getenv("CANDIDATES_FILE", "data/daily_candidates.json")

PORTFOLIO_FILE = os.getenv("PORTFOLIO_FILE", "data/portfolio.json")
