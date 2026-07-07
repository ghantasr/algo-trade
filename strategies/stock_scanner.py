from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
import yfinance as yf

from config.settings import INVESTMENT_PER_TRADE, LONG_MA, SHORT_MA
from trading.bucket import display_symbol
from trading.fees import break_even_pct, round_trip_fees
from utils.logger import logger


@dataclass
class BuyCandidate:
    symbol: str
    price: float
    quantity: int
    investment: float
    short_ma: float
    long_ma: float
    volume_ratio: float
    score: float
    reason: str
    break_even_pct: float
    estimated_fees: float
    target_profit_low: float
    target_profit_high: float


def _fetch_intraday(symbol: str, interval: str = "5m") -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="5d", interval=interval)
    return data


def _analyze_symbol(symbol: str, interval: str = "5m") -> Optional[BuyCandidate]:
    try:
        data = _fetch_intraday(symbol, interval)
        if data.empty or len(data) < LONG_MA + 5:
            return None

        close = data["Close"]
        volume = data["Volume"]

        short_ma = close.rolling(SHORT_MA).mean()
        long_ma = close.rolling(LONG_MA).mean()
        avg_vol = volume.rolling(20).mean()

        price = float(close.iloc[-1])
        cur_short = float(short_ma.iloc[-1])
        cur_long = float(long_ma.iloc[-1])
        prev_short = float(short_ma.iloc[-2])
        prev_long = float(long_ma.iloc[-2])
        cur_vol = float(volume.iloc[-1])
        cur_avg_vol = float(avg_vol.iloc[-1]) if avg_vol.iloc[-1] > 0 else 1

        volume_ratio = cur_vol / cur_avg_vol

        # Bullish: short MA above long MA, fresh crossover or strong trend
        crossover = prev_short <= prev_long and cur_short > cur_long
        uptrend = cur_short > cur_long and price > cur_short
        volume_ok = volume_ratio >= 1.1

        if not ((crossover or uptrend) and volume_ok):
            return None

        quantity = max(1, int(INVESTMENT_PER_TRADE / price))
        investment = quantity * price
        be_pct = break_even_pct(price, quantity)
        est_fees = round_trip_fees(price, price * 1.05, quantity)

        score = 0.0
        if crossover:
            score += 3.0
        if uptrend:
            score += 2.0
        score += min(volume_ratio, 3.0)
        score += (cur_short - cur_long) / cur_long * 100 if cur_long > 0 else 0

        reason_parts = []
        if crossover:
            reason_parts.append("MA bullish crossover")
        elif uptrend:
            reason_parts.append("Price above rising MAs")
        reason_parts.append(f"Volume {volume_ratio:.1f}x average")

        return BuyCandidate(
            symbol=symbol,
            price=price,
            quantity=quantity,
            investment=investment,
            short_ma=cur_short,
            long_ma=cur_long,
            volume_ratio=volume_ratio,
            score=score,
            reason=", ".join(reason_parts),
            break_even_pct=be_pct,
            estimated_fees=est_fees,
            target_profit_low=investment * 0.05,
            target_profit_high=investment * 0.10,
        )
    except Exception as e:
        logger.debug("Skip %s: %s", symbol, e)
        return None


def scan_for_buys(
    watchlist: List[str],
    exclude_symbols: List[str],
    interval: str = "5m",
    max_results: int = 2,
) -> List[BuyCandidate]:
    """Scan NSE watchlist and return top buy candidates."""
    candidates = []
    exclude = {s.upper() for s in exclude_symbols}

    for symbol in watchlist:
        if symbol.upper() in exclude:
            continue
        result = _analyze_symbol(symbol, interval)
        if result:
            candidates.append(result)

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:max_results]


def get_current_price(symbol: str) -> Optional[float]:
    try:
        data = _fetch_intraday(symbol)
        if data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except Exception:
        return None


def format_buy_recommendation(c: BuyCandidate) -> str:
    name = display_symbol(c.symbol)
    return (
        f"🟢 *BUY Recommendation*\n\n"
        f"Stock: *{name}*\n"
        f"Price: ₹{c.price:,.2f}\n"
        f"Suggested qty: *{c.quantity}* (≈₹{c.investment:,.0f})\n"
        f"Reason: {c.reason}\n\n"
        f"Est. fees (round trip): ₹{c.estimated_fees:.0f}\n"
        f"Break-even: +{c.break_even_pct:.2f}%\n"
        f"Target profit: ₹{c.target_profit_low:,.0f} – ₹{c.target_profit_high:,.0f} (5–10%)\n\n"
        f"👉 Buy on your broker, then confirm:\n"
        f"`/bought {name} {c.quantity} {c.price:.2f}`"
    )
