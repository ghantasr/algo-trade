"""
Momentum-based scanner — finds stocks already moving UP with profit potential.

Uses dynamically discovered stocks (not a fixed watchlist).
"""

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
import yfinance as yf

from config.settings import INVESTMENT_PER_TRADE, LONG_MA, MIN_GAIN_PCT, SHORT_MA
from data.market_discovery import DiscoveredStock, discover_market_stocks
from trading.bucket import display_symbol
from trading.fees import break_even_pct, round_trip_fees
from utils.logger import logger


@dataclass
class BuyCandidate:
    symbol: str
    price: float
    quantity: int
    investment: float
    change_pct: float
    volume_ratio: float
    momentum_score: float
    reason: str
    break_even_pct: float
    estimated_fees: float
    target_profit_low: float
    target_profit_high: float
    source: str


def _fetch_intraday(symbol: str, interval: str = "5m") -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    return ticker.history(period="5d", interval=interval)


def _is_still_rising(data: pd.DataFrame) -> tuple:
    """
    Check if stock is going UP (not falling).
    Returns (is_rising, drop_from_high_pct, reason_parts)
    """
    close = data["Close"]
    high = data["High"]

    price = float(close.iloc[-1])
    day_high = float(high.max())
    drop_from_high = ((day_high - price) / day_high * 100) if day_high > 0 else 0

    # Last 3 candles should be mostly green (closing higher)
    last_3 = close.iloc[-3:]
    green_candles = sum(1 for i in range(1, len(last_3)) if last_3.iloc[i] >= last_3.iloc[i - 1])

    short_ma = close.rolling(SHORT_MA).mean()
    cur_short = float(short_ma.iloc[-1])
    above_ma = price >= cur_short

    reasons = []
    rising = True

    if drop_from_high > 1.5:
        rising = False
        reasons.append(f"falling {drop_from_high:.1f}% from day high")
    elif drop_from_high > 0.8:
        reasons.append(f"slight pullback {drop_from_high:.1f}% from high")

    if green_candles < 1:
        rising = False
        reasons.append("last candles turning red")

    if not above_ma:
        rising = False
        reasons.append("price below short MA")

    if rising:
        reasons.append("momentum still up")

    return rising, drop_from_high, reasons


def analyze_momentum(
    stock: DiscoveredStock,
    interval: str = "5m",
) -> Optional[BuyCandidate]:
    """
    Deep-check a discovered stock:
    - Must be in profit today (gain % > minimum)
    - Must still be rising (not falling)
    - Must have enough move left to cover broker fees + target profit
    """
    try:
        data = _fetch_intraday(stock.symbol, interval)
        if data.empty or len(data) < LONG_MA + 3:
            return None

        close = data["Close"]
        volume = data["Volume"]

        price = float(close.iloc[-1])
        if price <= 0:
            return None

        today = data[data.index.date == data.index[-1].date()]
        if today.empty:
            return None

        open_price = float(today["Open"].iloc[0])
        change_pct = ((price - open_price) / open_price) * 100

        if change_pct < MIN_GAIN_PCT:
            return None

        rising, drop_from_high, trend_reasons = _is_still_rising(data)
        if not rising:
            logger.debug("Skip %s: not rising — %s", stock.symbol, trend_reasons)
            return None

        avg_vol = volume.rolling(20).mean()
        cur_vol = float(volume.iloc[-1])
        avg = float(avg_vol.iloc[-1]) if avg_vol.iloc[-1] > 0 else 1
        volume_ratio = cur_vol / avg

        quantity = max(1, int(INVESTMENT_PER_TRADE / price))
        investment = quantity * price
        be_pct = break_even_pct(price, quantity)

        # Must have already gained more than break-even + buffer
        if change_pct < be_pct + 0.3:
            return None

        est_fees = round_trip_fees(price, price * 1.05, quantity)

        momentum_score = (
            change_pct * 2
            + min(volume_ratio, 3)
            + stock.score
            - drop_from_high
        )

        reason = (
            f"Up {change_pct:.1f}% today, {', '.join(trend_reasons)}, "
            f"Volume {volume_ratio:.1f}x avg, source: {stock.source}"
        )

        return BuyCandidate(
            symbol=stock.symbol,
            price=price,
            quantity=quantity,
            investment=investment,
            change_pct=change_pct,
            volume_ratio=volume_ratio,
            momentum_score=momentum_score,
            reason=reason,
            break_even_pct=be_pct,
            estimated_fees=est_fees,
            target_profit_low=investment * 0.05,
            target_profit_high=investment * 0.10,
            source=stock.source,
        )
    except Exception as e:
        logger.debug("Analyze failed %s: %s", stock.symbol, e)
        return None


def scan_momentum_buys(
    exclude_symbols: List[str],
    interval: str = "5m",
    max_results: int = 2,
    pre_market: bool = False,
) -> tuple:
    """
    1. Discover top movers from NSE / Moneycontrol / NIFTY scan
    2. Filter for stocks still going UP with fee-adjusted profit potential
    """
    discovered = discover_market_stocks(pre_market=pre_market, limit=25)
    exclude = {s.upper() for s in exclude_symbols}

    candidates = []
    for stock in discovered:
        if stock.symbol.upper() in exclude:
            continue
        result = analyze_momentum(stock, interval)
        if result:
            candidates.append(result)

    candidates.sort(key=lambda c: c.momentum_score, reverse=True)
    return candidates[:max_results], discovered


def get_current_price(symbol: str) -> Optional[float]:
    try:
        data = _fetch_intraday(symbol)
        if data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except Exception:
        return None


def get_intraday_high(symbol: str) -> Optional[float]:
    try:
        data = _fetch_intraday(symbol)
        if data.empty:
            return None
        today = data[data.index.date == data.index[-1].date()]
        if today.empty:
            return float(data["High"].max())
        return float(today["High"].max())
    except Exception:
        return None


def is_falling(symbol: str, entry_price: float) -> tuple:
    """
    Detect if a stock is falling down.
    Returns (is_falling: bool, reason: str, drop_from_high_pct: float)
    """
    try:
        data = _fetch_intraday(symbol)
        if data.empty or len(data) < 4:
            return False, "", 0.0

        close = data["Close"]
        price = float(close.iloc[-1])
        day_high = float(data["High"].max())
        drop_from_high = ((day_high - price) / day_high * 100) if day_high > 0 else 0

        # Last 2 candles declining
        c1, c2 = float(close.iloc[-2]), float(close.iloc[-1])
        two_red = c2 < c1

        short_ma = close.rolling(SHORT_MA).mean()
        below_ma = price < float(short_ma.iloc[-1])

        short_ma_falling = float(short_ma.iloc[-1]) < float(short_ma.iloc[-3])

        reasons = []
        falling = False

        if drop_from_high >= 1.0 and two_red:
            falling = True
            reasons.append(f"dropped {drop_from_high:.1f}% from high + red candles")

        if below_ma and short_ma_falling:
            falling = True
            reasons.append("price below falling MA")

        if price < entry_price and two_red:
            falling = True
            reasons.append("below your entry + selling pressure")

        reason = ", ".join(reasons) if reasons else "holding steady"
        return falling, reason, drop_from_high
    except Exception:
        return False, "", 0.0


def format_buy_recommendation(c: BuyCandidate) -> str:
    name = display_symbol(c.symbol)
    return (
        f"🟢 *BUY — Momentum Pick*\n\n"
        f"Stock: *{name}*\n"
        f"Price: ₹{c.price:,.2f}\n"
        f"Today: *+{c.change_pct:.1f}%* (already in profit)\n"
        f"Suggested qty: *{c.quantity}* (≈₹{c.investment:,.0f})\n"
        f"Reason: {c.reason}\n\n"
        f"Est. fees: ₹{c.estimated_fees:.0f} | Break-even: +{c.break_even_pct:.2f}%\n"
        f"Target after fees: ₹{c.target_profit_low:,.0f} – ₹{c.target_profit_high:,.0f} (5–10%)\n\n"
        f"👉 Buy on broker, then:\n"
        f"`/bought {name} {c.quantity} {c.price:.2f}`"
    )


def format_discovery_summary(discovered: list, pre_market: bool = False) -> str:
    label = "Pre-Market Scan" if pre_market else "Live Market Scan"
    lines = [f"📡 *{label}* — top movers from NSE / Moneycontrol\n"]
    for i, s in enumerate(discovered[:10], 1):
        pct = f"+{s.change_pct:.1f}%" if s.change_pct else "—"
        lines.append(f"{i}. *{s.name}* {pct} ({s.source})")
    lines.append("\nAnalysing which ones are still rising...")
    return "\n".join(lines)
