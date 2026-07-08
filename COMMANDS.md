# Algo-Trade Bot — Commands Reference

## Setup

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your .env file
cp .env.example .env
# Then edit .env with your Telegram bot token and chat ID
```

## Running the Bot

```bash
# Activate venv first (if not already active)
source .venv/bin/activate

# Run the main bot (starts Telegram polling + advisory loop)
python main.py
```

## Testing the Pre-Market Analyzer

```bash
# Activate venv
source .venv/bin/activate

# Run the pre-market analyzer test script
python scripts/test_premarket.py
```

This will:
1. Fetch live NSE data (top gainers, most active stocks)
2. Run the pre-market analyzer with profit predictions
3. Print the formatted report with:
   - Gap-up percentage
   - Conservative & optimistic profit predictions
   - Success probability & risk metrics
   - Overall score (0-10)

> **Note**: If NSE is closed (outside 9:00 AM - 3:30 PM IST), the script will automatically use sample data to demonstrate the analyzer.

## Other Test Scripts

```bash
# Test market data fetching
python scripts/test_market_data.py

# Test momentum scanner
python scripts/test_scanner.py

# Test Telegram messaging
python scripts/test_telegram.py
```

## Git Workflow

```bash
# View current branch
git branch

# Switch to master branch (original code)
git checkout master

# Switch to feature branch (pre-market analyzer)
git checkout feature/premarket-analysis

# View commit history
git log --oneline --all

# See what changed in the latest commit
git show HEAD --stat
```

## Configuration Options (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | — | Your bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | — | Your Telegram user ID |
| `INVESTMENT_PER_TRADE` | 10000 | ₹ per stock suggestion |
| `TARGET_PROFIT_PCT` | 5 | Profit target after fees (%) |
| `MAX_PROFIT_PCT` | 10 | Max profit before auto-sell (%) |
| `STOP_LOSS_PCT` | 2 | Stop loss after fees (%) |
| `EXIT_MINUTES_BEFORE_CLOSE` | 60 | Exit before 3:30 PM (minutes) |
| `CHECK_INTERVAL` | 120 | Scan interval (seconds) |
| `MAX_POSITIONS` | 3 | Max stocks in bucket |
| `MAX_BUY_SUGGESTIONS` | 2 | Max buy suggestions per scan |
| `PREDICTION_LOOKBACK_DAYS` | 20 | Days of history for profit predictions |
| `PREMARKET_ONLY` | false | Skip live scanning, only pre-market analysis |
