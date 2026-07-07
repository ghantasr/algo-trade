#!/usr/bin/env python3
"""
Quick test: fetches market data for your configured symbol.
Run this to verify Yahoo Finance data works.

Usage:
    python scripts/test_market_data.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import INTERVAL, LONG_MA, SHORT_MA, SYMBOL, TRADING_MODE
from strategies.ma_crossover import moving_average_crossover


def main():
    print(f"Fetching market data for {SYMBOL} ({TRADING_MODE} mode)...")
    result = moving_average_crossover(
        SYMBOL,
        short_window=SHORT_MA,
        long_window=LONG_MA,
        trading_mode=TRADING_MODE,
        interval=INTERVAL,
    )

    print(f"\n  Signal:    {result.signal.value}")
    print(f"  Price:     ${result.price:,.2f}")
    print(f"  Short MA:  ${result.short_ma:,.2f}")
    print(f"  Long MA:   ${result.long_ma:,.2f}")
    print(f"  Reason:    {result.reason}")
    print("\nMarket data is working!")


if __name__ == "__main__":
    main()
