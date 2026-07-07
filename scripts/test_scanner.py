#!/usr/bin/env python3
"""Test live market discovery from NSE / Moneycontrol / NIFTY scan."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.market_discovery import discover_market_stocks
from strategies.momentum_scanner import format_buy_recommendation, scan_momentum_buys


def main():
    print("=" * 50)
    print("STEP 1: Discovering stocks from financial websites...")
    print("=" * 50)

    discovered = discover_market_stocks(pre_market=False, limit=15)
    if not discovered:
        print("No stocks discovered. Check internet / try during market hours.")
        return

    for i, s in enumerate(discovered, 1):
        pct = f"+{s.change_pct:.1f}%" if s.change_pct else "—"
        print(f"  {i:2}. {s.name:15} {pct:8}  source={s.source}")

    print()
    print("=" * 50)
    print("STEP 2: Filtering for momentum + fee-adjusted profit...")
    print("=" * 50)

    candidates, _ = scan_momentum_buys([], max_results=5)
    if not candidates:
        print("No stocks passing momentum checks right now.")
        print("(Stocks must be UP today, still rising, and profitable after fees)")
        return

    for c in candidates:
        print()
        print(format_buy_recommendation(c).replace("*", ""))


if __name__ == "__main__":
    main()
