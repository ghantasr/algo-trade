from dataclasses import dataclass
from enum import Enum
from typing import Tuple

import pandas as pd
import yfinance as yf

from utils.logger import logger


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategyResult:
    signal: Signal
    price: float
    short_ma: float
    long_ma: float
    reason: str


def fetch_price_data(
    symbol: str,
    period: str = "3mo",
    interval: str = "1d",
) -> pd.DataFrame:
    """Download price history from Yahoo Finance."""
    ticker = yf.Ticker(symbol)
    data = ticker.history(period=period, interval=interval)

    if data.empty:
        raise ValueError(f"No data found for symbol: {symbol}")

    return data


def _data_params(trading_mode: str, interval: str) -> Tuple[str, str]:
    """Pick yfinance period/interval based on trading mode."""
    if trading_mode == "intraday":
        # yfinance limits: 1m → 7 days, 5m/15m → up to 60 days
        period_map = {"1m": "5d", "5m": "5d", "15m": "10d", "30m": "10d", "1h": "30d"}
        period = period_map.get(interval, "5d")
        return period, interval
    return "3mo", "1d"


def moving_average_crossover(
    symbol: str,
    short_window: int = 10,
    long_window: int = 30,
    trading_mode: str = "swing",
    interval: str = "5m",
) -> StrategyResult:
    """
    Simple strategy: buy when short MA crosses above long MA, sell when it crosses below.

    For swing mode, windows are in days. For intraday, windows are number of candles.
    """
    period, candle_interval = _data_params(trading_mode, interval)
    data = fetch_price_data(symbol, period=period, interval=candle_interval)
    close = data["Close"]

    if len(close) < long_window + 2:
        raise ValueError(
            f"Not enough candles ({len(close)}) for long MA window ({long_window}). "
            f"Try a shorter LONG_MA or different INTERVAL."
        )

    short_ma = close.rolling(window=short_window).mean()
    long_ma = close.rolling(window=long_window).mean()

    current_price = float(close.iloc[-1])
    current_short = float(short_ma.iloc[-1])
    current_long = float(long_ma.iloc[-1])
    prev_short = float(short_ma.iloc[-2])
    prev_long = float(long_ma.iloc[-2])

    mode_label = f"{candle_interval} candle" if trading_mode == "intraday" else "daily"

    if prev_short <= prev_long and current_short > current_long:
        signal = Signal.BUY
        reason = f"[{mode_label}] Short MA ({current_short:.2f}) crossed above Long MA ({current_long:.2f})"
    elif prev_short >= prev_long and current_short < current_long:
        signal = Signal.SELL
        reason = f"[{mode_label}] Short MA ({current_short:.2f}) crossed below Long MA ({current_long:.2f})"
    else:
        signal = Signal.HOLD
        reason = (
            f"[{mode_label}] No crossover. Price: {current_price:.2f}, "
            f"Short MA: {current_short:.2f}, Long MA: {current_long:.2f}"
        )

    logger.info("Strategy result for %s: %s — %s", symbol, signal.value, reason)

    return StrategyResult(
        signal=signal,
        price=current_price,
        short_ma=current_short,
        long_ma=current_long,
        reason=reason,
    )
