"""
Pre-market analyzer — analyses stocks before market open and predicts profit potential.

Uses historical intraday data to estimate:
  - How much a stock typically gains after gapping up by X%
  - Probability of hitting profit targets
  - Risk of gap filling / reversing
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from config.settings import (
    INVESTMENT_PER_TRADE,
    PREDICTION_LOOKBACK_DAYS,
    TARGET_PROFIT_PCT,
    STOP_LOSS_PCT,
)
from data.market_discovery import DiscoveredStock
from trading.bucket import display_symbol
from trading.fees import break_even_pct, round_trip_fees
from utils.logger import logger


@dataclass
class ProfitPrediction:
    """Predicted profit range based on historical gap-up behaviour."""

    conservative_pct: float       # e.g. 5.2%
    conservative_profit: float    # e.g. ₹510
    optimistic_pct: float         # e.g. 9.8%
    optimistic_profit: float      # e.g. ₹960
    probability_hit_target: float # 0-1, e.g. 0.75 = 75% chance of hitting 5% profit
    probability_hit_stop: float   # 0-1, e.g. 0.15 = 15% chance of hitting -2% loss
    avg_additional_gain: float    # avg % gain AFTER the gap-up open
    sample_size: int              # how many historical gap-up days were analysed


@dataclass
class PremarketPick:
    """A stock recommended during pre-market analysis with profit predictions."""

    symbol: str
    name: str
    pre_open_price: float
    gap_pct: float                # % gap up from yesterday's close
    volume: float
    score: float                  # overall score (0-10)
    prediction: ProfitPrediction
    suggested_quantity: int
    investment: float
    break_even_pct: float
    estimated_fees: float
    reason: str


def _fetch_historical_data(symbol: str, days: int = 20) -> pd.DataFrame:
    """Fetch intraday data for the last N days."""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=f"{days + 5}d", interval="15m")
        if data.empty:
            data = ticker.history(period=f"{days + 5}d", interval="5m")
        return data
    except Exception as e:
        logger.debug("Failed to fetch history for %s: %s", symbol, e)
        return pd.DataFrame()


def _get_yesterday_close(symbol: str) -> Optional[float]:
    """Get yesterday's closing price."""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="5d", interval="1d")
        if data.empty or len(data) < 2:
            return None
        return float(data["Close"].iloc[-2])
    except Exception:
        return None


def _find_gap_up_days(
    data: pd.DataFrame,
    min_gap_pct: float = 0.5,
) -> List[dict]:
    """
    Find historical days where the stock gapped up.
    Returns list of dicts with gap-up info and subsequent performance.
    """
    if data.empty or len(data) < 10:
        return []

    gap_days = []
    # Group by date
    data = data.copy()
    data["date"] = data.index.date

    for date, day_data in data.groupby("data.date"):
        if len(day_data) < 3:
            continue

        day_data = day_data.sort_index()
        open_price = float(day_data["Open"].iloc[0])
        close_price = float(day_data["Close"].iloc[-1])
        high_price = float(day_data["High"].max())
        low_price = float(day_data["Low"].min())

        # We need previous day's close to calculate gap
        # Since we have multi-day data, the first candle's open vs prev close
        # But yfinance gives continuous data, so we approximate:
        # The gap is open vs previous candle's close (if different day)
        prev_close = float(day_data["Close"].iloc[0])  # last close of prev day

        gap_pct = ((open_price - prev_close) / prev_close) * 100

        if gap_pct < min_gap_pct:
            continue

        # Calculate subsequent move after open
        subsequent_high_pct = ((high_price - open_price) / open_price) * 100
        subsequent_low_pct = ((low_price - open_price) / open_price) * 100
        subsequent_close_pct = ((close_price - open_price) / open_price) * 100

        gap_days.append({
            "date": date,
            "gap_pct": gap_pct,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "subsequent_high_pct": subsequent_high_pct,
            "subsequent_low_pct": subsequent_low_pct,
            "subsequent_close_pct": subsequent_close_pct,
        })

    return gap_days


def _find_similar_gap_days(
    gap_days: List[dict],
    current_gap_pct: float,
    tolerance: float = 0.5,
) -> List[dict]:
    """Find historical gap-up days similar to the current gap-up size."""
    similar = []
    for day in gap_days:
        if abs(day["gap_pct"] - current_gap_pct) <= tolerance:
            similar.append(day)
    # If too few matches, widen tolerance
    if len(similar) < 3:
        similar = [d for d in gap_days if abs(d["gap_pct"] - current_gap_pct) <= tolerance * 2]
    # If still too few, use all gap-up days
    if len(similar) < 3:
        similar = gap_days
    return similar


def predict_profit(
    stock: DiscoveredStock,
    yesterday_close: float,
) -> Optional[PremarketPick]:
    """
    Analyse a pre-market stock and predict profit potential.
    
    1. Calculate gap-up percentage from yesterday's close
    2. Fetch historical intraday data
    3. Find similar gap-up days in history
    4. Calculate predicted profit ranges
    5. Return a PremarketPick with all predictions
    """
    if yesterday_close <= 0:
        return None

    gap_pct = ((stock.price - yesterday_close) / yesterday_close) * 100

    # Only consider stocks gapping up
    if gap_pct < 0.3:
        return None

    # Fetch historical data
    hist_data = _fetch_historical_data(stock.symbol, PREDICTION_LOOKBACK_DAYS)
    gap_days = _find_gap_up_days(hist_data, min_gap_pct=0.3)

    # Calculate predictions
    if gap_days:
        similar_days = _find_similar_gap_days(gap_days, gap_pct)
        sample_size = len(similar_days)

        if similar_days:
            subsequent_gains = [d["subsequent_high_pct"] for d in similar_days]
            subsequent_losses = [abs(d["subsequent_low_pct"]) for d in similar_days if d["subsequent_low_pct"] < 0]
            subsequent_closes = [d["subsequent_close_pct"] for d in similar_days]

            avg_additional_gain = float(np.mean(subsequent_gains)) if subsequent_gains else 1.0
            # Conservative: 25th percentile of subsequent gains
            conservative_pct = max(float(np.percentile(subsequent_gains, 25)), TARGET_PROFIT_PCT)
            # Optimistic: 75th percentile
            optimistic_pct = float(np.percentile(subsequent_gains, 75))

            # Probability of hitting target profit
            hits_target = sum(1 for g in subsequent_gains if g >= TARGET_PROFIT_PCT)
            probability_hit_target = hits_target / len(subsequent_gains) if subsequent_gains else 0.5

            # Probability of hitting stop loss
            hits_stop = sum(1 for l in subsequent_losses if l >= STOP_LOSS_PCT)
            probability_hit_stop = hits_stop / len(subsequent_losses) if subsequent_losses else 0.1
        else:
            # Fallback if no similar days
            avg_additional_gain = 2.0
            conservative_pct = TARGET_PROFIT_PCT
            optimistic_pct = TARGET_PROFIT_PCT * 2
            probability_hit_target = 0.5
            probability_hit_stop = 0.2
            sample_size = 0
    else:
        # No historical gap-up data — use conservative defaults
        avg_additional_gain = 1.5
        conservative_pct = TARGET_PROFIT_PCT
        optimistic_pct = TARGET_PROFIT_PCT * 1.5
        probability_hit_target = 0.4
        probability_hit_stop = 0.25
        sample_size = 0

    # Calculate investment details
    quantity = max(1, int(INVESTMENT_PER_TRADE / stock.price))
    investment = quantity * stock.price
    be_pct = break_even_pct(stock.price, quantity)
    est_fees = round_trip_fees(stock.price, stock.price * 1.05, quantity)

    conservative_profit = investment * (conservative_pct / 100)
    optimistic_profit = investment * (optimistic_pct / 100)

    # Overall score (0-10)
    score = min(10.0, (
        min(gap_pct * 1.5, 3.0)           # Gap-up size (max 3 pts)
        + probability_hit_target * 3.0     # Probability of success (max 3 pts)
        + min(avg_additional_gain, 3.0)    # Historical gain potential (max 3 pts)
        + (1.0 - probability_hit_stop)     # Low risk (max 1 pt)
    ))

    prediction = ProfitPrediction(
        conservative_pct=round(conservative_pct, 2),
        conservative_profit=round(conservative_profit, 0),
        optimistic_pct=round(optimistic_pct, 2),
        optimistic_profit=round(optimistic_profit, 0),
        probability_hit_target=round(probability_hit_target, 2),
        probability_hit_stop=round(probability_hit_stop, 2),
        avg_additional_gain=round(avg_additional_gain, 2),
        sample_size=sample_size,
    )

    reason_parts = []
    if gap_pct >= 2:
        reason_parts.append(f"Strong gap-up of {gap_pct:.1f}%")
    elif gap_pct >= 1:
        reason_parts.append(f"Healthy gap-up of {gap_pct:.1f}%")
    else:
        reason_parts.append(f"Mild gap-up of {gap_pct:.1f}%")

    if probability_hit_target >= 0.7:
        reason_parts.append("high historical success rate")
    elif probability_hit_target >= 0.5:
        reason_parts.append("moderate historical success rate")

    if sample_size > 0:
        reason_parts.append(f"based on {sample_size} similar gap-up days")
    else:
        reason_parts.append("limited historical data — trade cautiously")

    return PremarketPick(
        symbol=stock.symbol,
        name=stock.name,
        pre_open_price=stock.price,
        gap_pct=round(gap_pct, 2),
        volume=stock.volume,
        score=round(score, 1),
        prediction=prediction,
        suggested_quantity=quantity,
        investment=round(investment, 0),
        break_even_pct=round(be_pct, 2),
        estimated_fees=round(est_fees, 0),
        reason=", ".join(reason_parts),
    )


def analyze_premarket_stocks(
    discovered: List[DiscoveredStock],
    max_results: int = 5,
) -> List[PremarketPick]:
    """
    Analyse all discovered pre-market stocks and return ranked picks with predictions.
    """
    picks = []
    for stock in discovered:
        yesterday_close = _get_yesterday_close(stock.symbol)
        if yesterday_close is None:
            continue
        pick = predict_profit(stock, yesterday_close)
        if pick:
            picks.append(pick)

    # Sort by score descending
    picks.sort(key=lambda p: p.score, reverse=True)
    return picks[:max_results]


def format_premarket_report(picks: List[PremarketPick]) -> str:
    """Format the pre-market analysis report for Telegram."""
    if not picks:
        return (
            "🌅 *Pre-Market Analysis Complete*\n\n"
            "No strong picks found today. Stocks are either not gapping up "
            "significantly or historical data shows low probability of success.\n\n"
            "I'll continue scanning during market hours — send /scan to check."
        )

    lines = [
        "🌅 *Pre-Market Analysis — Top Picks for Today*\n",
        f"Analysed {len(picks)} stocks with strong gap-up signals\n",
    ]

    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    for i, pick in enumerate(picks):
        emoji = emojis[i] if i < len(emojis) else "•"
        name = display_symbol(pick.symbol)
        score_bar = "⭐" * max(1, int(pick.score / 2))

        lines.extend([
            f"{emoji} *{name}* — Gap Up: *+{pick.gap_pct:.1f}%*",
            f"   Pre-open: ₹{pick.pre_open_price:,.2f} | "
            f"Suggested: *{pick.suggested_quantity} shares* (₹{pick.investment:,.0f})",
            f"   {score_bar} Score: {pick.score}/10",
            f"",
            f"   📈 *Profit Prediction* "
            f"{'(based on ' + str(pick.prediction.sample_size) + ' similar gap-up days)' if pick.prediction.sample_size > 0 else '(limited data)'}",
            f"   • Conservative: *+{pick.prediction.conservative_pct:.1f}%* "
            f"(₹{pick.prediction.conservative_profit:,.0f})",
            f"   • Optimistic: *+{pick.prediction.optimistic_pct:.1f}%* "
            f"(₹{pick.prediction.optimistic_profit:,.0f})",
            f"   • Success rate: {pick.prediction.probability_hit_target * 100:.0f}% chance of hitting target",
            f"   • Risk: {pick.prediction.probability_hit_stop * 100:.0f}% chance of hitting stop-loss",
            f"",
            f"   💡 {pick.reason}",
            f"   Est. fees: ₹{pick.estimated_fees:,.0f} | Break-even: +{pick.break_even_pct:.2f}%",
            f"",
            f"   👉 Buy on broker, then: `/bought {name} {pick.suggested_quantity} {pick.pre_open_price:.2f}`",
            f"",
        ])

    lines.append(
        "📌 *How to use:*\n"
        "1. Review the picks above\n"
        "2. Buy on your broker if you agree\n"
        "3. Confirm with `/bought` command\n"
        "4. I'll alert you when to sell (target/stop-loss)\n\n"
        "Send /scan during market hours for live picks."
    )

    return "\n".join(lines)
