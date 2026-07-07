# Algo Trade — NSE Intraday Advisory Bot

An **Indian stock market (NSE) intraday advisor** that runs on Telegram.

**You trade manually on your broker (Zerodha, Groww, etc.).** The bot analyses the market, tells you what to buy/sell, tracks your positions, and includes broker fees in profit calculations.

---

## How It Works

```
Bot scans NSE stocks
        ↓
Sends BUY recommendation on Telegram
        ↓
YOU buy on your broker app
        ↓
YOU confirm: /bought RELIANCE 4 2450
        ↓
Bot tracks in your "bucket"
        ↓
Bot monitors price → sends SELL alert when:
  • 5–10% profit (after fees) ✅
  • Losing money (stop loss) 🔴
  • 1 hour before market close ⏰
        ↓
YOU sell on broker → confirm: /sold RELIANCE 4 2580
```

---

## Setup (Step by Step)

### 1. Create Telegram Bot
1. Message **@BotFather** → `/newbot` → save your **token**
2. Message **@userinfobot** → save your **chat ID**
3. Open your bot and tap **Start**

### 2. Install
```bash
cd /Users/apple/Desktop/applications/algo-trade
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 3. Edit `.env`
```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_id
INVESTMENT_PER_TRADE=10000
TARGET_PROFIT_PCT=5
EXIT_MINUTES_BEFORE_CLOSE=60
```

### 4. Test & Run
```bash
python scripts/test_telegram.py
python main.py
```

Send `/run` on Telegram during market hours (9:15 AM – 3:30 PM IST).

---

## Telegram Commands

| Command | What it does |
|---------|--------------|
| `/run` | Start scanning NSE stocks |
| `/stop` | Pause scanning |
| `/scan` | Scan for buy opportunities now |
| `/bucket` | Show your holdings & P&L (after fees) |
| `/bought SYMBOL QTY PRICE` | Confirm you bought (adds to bucket) |
| `/sold SYMBOL QTY PRICE` | Confirm you sold (removes from bucket) |
| `/help` | Show all commands |

### Example Session

**Bot sends:**
```
🟢 BUY Recommendation

Stock: RELIANCE
Price: ₹2,450.00
Suggested qty: 4 (≈₹9,800)
Reason: MA bullish crossover, Volume 1.5x average

Est. fees (round trip): ₹49
Break-even: +0.50%
Target profit: ₹490 – ₹980 (5–10%)

👉 Buy on your broker, then confirm:
/bought RELIANCE 4 2450.00
```

**You buy on Zerodha, then reply:**
```
/bought RELIANCE 4 2450
```

**Later, bot sends:**
```
🔴 SELL Alert — RELIANCE

Your entry: ₹2,450 × 4
Current price: ₹2,580
Net P&L: +₹471 (+4.8% after fees)

Reason: ✅ Target hit — 5%+ profit after fees!

/sold RELIANCE 4 2580
```

**At 2:30 PM (1 hr before close):**
```
⏰ EXIT ALL POSITIONS NOW
Market closes in 60 minutes

[shows all holdings with P&L]

/sold SYMBOL QTY PRICE for each
```

---

## Broker Fees Included

The bot calculates **Zerodha-style intraday fees**:
- Brokerage (₹20/order or 0.03%)
- STT, exchange charges, GST, stamp duty

Profit/loss numbers you see are **after fees**, so you know your real gain.

---

## Settings Reference

| Setting | Default | Meaning |
|---------|---------|---------|
| `INVESTMENT_PER_TRADE` | 10000 | ₹ per stock suggestion |
| `TARGET_PROFIT_PCT` | 5 | Alert to sell at 5%+ profit |
| `MAX_PROFIT_PCT` | 10 | Strong sell alert at 10%+ |
| `STOP_LOSS_PCT` | 2 | Alert to sell if losing 2%+ |
| `EXIT_MINUTES_BEFORE_CLOSE` | 60 | Exit all by 2:30 PM IST |
| `MAX_POSITIONS` | 3 | Max stocks in bucket |
| `CHECK_INTERVAL` | 120 | Scan every 2 minutes |
| `WATCHLIST` | 10 NSE stocks | Comma-separated symbols |

---

## Important Notes

- **Not a broker** — the bot does NOT place orders. You trade manually.
- **Paper advisory** — recommendations are based on free Yahoo Finance data (15–20 min delay).
- **5–10% daily is ambitious** — intraday targets vary; use this to learn, not as guaranteed returns.
- **NSE hours only** — 9:15 AM to 3:30 PM IST, Monday–Friday.
- **Mandatory intraday exit** — bot reminds you to sell everything 1 hour before close.

---

## Disclaimer

This is an educational tool, not financial advice. Intraday trading involves significant risk. Never invest money you cannot afford to lose.
