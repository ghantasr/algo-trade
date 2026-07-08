"""
Test script for the pre-market analyzer with profit predictions.

Usage:
    python scripts/test_premarket.py

This will:
1. Fetch NSE pre-open / gainers data
2. Run the pre-market analyzer with profit predictions
3. Print the formatted report
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.market_discovery import discover_market_stocks
from strategies.premarket_analyzer import (
    analyze_premarket_stocks,
    format_premarket_report,
)
from config.settings import MAX_BUY_SUGGESTIONS


def main():
    print("=" * 60)
    print("🌅 PRE-MARKET ANALYZER TEST")
    print("=" * 60)

    # Step 1: Discover stocks from NSE
    print("\n📡 Step 1: Discovering stocks from NSE...")
    discovered = discover_market_stocks(pre_market=False, limit=25)
    print(f"   Found {len(discovered)} stocks")

    if not discovered:
        print("\n❌ No stocks discovered. NSE might be closed or API unavailable.")
        print("   This is normal outside market hours (9:00 AM - 3:30 PM IST).")
        print("\n   The script will now use sample data to demonstrate the analyzer.")
        _run_with_sample_data()
        return

    # Print discovered stocks
    print(f"\n   Top stocks discovered:")
    for i, s in enumerate(discovered[:10], 1):
        pct = f"+{s.change_pct:.1f}%" if s.change_pct else "—"
        print(f"   {i}. {s.name} ({s.symbol}) — {pct} — source: {s.source}")

    # Step 2: Run pre-market analyzer
    print(f"\n📊 Step 2: Running pre-market analyzer with profit predictions...")
    picks = analyze_premarket_stocks(discovered, max_results=MAX_BUY_SUGGESTIONS)
    print(f"   Generated {len(picks)} picks with predictions\n")

    # Step 3: Print the report
    print("=" * 60)
    print("📋 PRE-MARKET REPORT")
    print("=" * 60)
    print()
    print(format_premarket_report(picks))
    print()
    print("=" * 60)

    # Print detailed stats for each pick
    if picks:
        print("\n📈 DETAILED STATS:")
        print("-" * 60)
        for pick in picks:
            print(f"\n{pick.name} ({pick.symbol}):")
            print(f"   Gap-up: +{pick.gap_pct:.1f}%")
            print(f"   Pre-open price: ₹{pick.pre_open_price:,.2f}")
            print(f"   Score: {pick.score}/10")
            print(f"   Suggested: {pick.suggested_quantity} shares @ ₹{pick.investment:,.0f}")
            print(f"   Conservative profit: +{pick.prediction.conservative_pct:.1f}% (₹{pick.prediction.conservative_profit:,.0f})")
            print(f"   Optimistic profit: +{pick.prediction.optimistic_pct:.1f}% (₹{pick.prediction.optimistic_profit:,.0f})")
            print(f"   Success rate: {pick.prediction.probability_hit_target * 100:.0f}%")
            print(f"   Risk: {pick.prediction.probability_hit_stop * 100:.0f}%")
            print(f"   Sample size: {pick.prediction.sample_size} days")
            print(f"   Reason: {pick.reason}")


def _run_with_sample_data():
    """Run the analyzer with sample data for demonstration."""
    print("\n📋 Running with sample data for demonstration...\n")

    from data.market_discovery import DiscoveredStock

    # Sample stocks that might be discovered on a typical day
    sample_stocks = [
        DiscoveredStock(
            symbol="RELIANCE.NS", name="RELIANCE",
            price=2450.00, change_pct=2.3, volume=2500000,
            source="nse_preopen", score=2.3,
        ),
        DiscoveredStock(
            symbol="TCS.NS", name="TCS",
            price=3850.00, change_pct=1.8, volume=1800000,
            source="nse_preopen", score=1.8,
        ),
        DiscoveredStock(
            symbol="HDFCBANK.NS", name="HDFCBANK",
            price=1680.00, change_pct=1.5, volume=3200000,
            source="nse_gainers", score=1.5,
        ),
        DiscoveredStock(
            symbol="INFY.NS", name="INFY",
            price=1520.00, change_pct=1.2, volume=2100000,
            source="nse_gainers", score=1.2,
        ),
        DiscoveredStock(
            symbol="ICICIBANK.NS", name="ICICIBANK",
            price=1120.00, change_pct=0.9, volume=2800000,
            source="nse_gainers", score=0.9,
        ),
    ]

    print(f"   Sample stocks loaded: {len(sample_stocks)}")
    for s in sample_stocks:
        print(f"   • {s.name} ({s.symbol}) — +{s.change_pct:.1f}%")

    picks = analyze_premarket_stocks(sample_stocks, max_results=3)
    print(f"\n   Generated {len(picks)} picks with predictions\n")

    print("=" * 60)
    print("📋 SAMPLE PRE-MARKET REPORT")
    print("=" * 60)
    print()
    print(format_premarket_report(picks))
    print()
    print("=" * 60)

    if picks:
        print("\n📈 DETAILED STATS:")
        print("-" * 60)
        for pick in picks:
            print(f"\n{pick.name} ({pick.symbol}):")
            print(f"   Gap-up: +{pick.gap_pct:.1f}%")
            print(f"   Pre-open price: ₹{pick.pre_open_price:,.2f}")
            print(f"   Score: {pick.score}/10")
            print(f"   Suggested: {pick.suggested_quantity} shares @ ₹{pick.investment:,.0f}")
            print(f"   Conservative profit: +{pick.prediction.conservative_pct:.1f}% (₹{pick.prediction.conservative_profit:,.0f})")
            print(f"   Optimistic profit: +{pick.prediction.optimistic_pct:.1f}% (₹{pick.prediction.optimistic_profit:,.0f})")
            print(f"   Success rate: {pick.prediction.probability_hit_target * 100:.0f}%")
            print(f"   Risk: {pick.prediction.probability_hit_stop * 100:.0f}%")
            print(f"   Sample size: {pick.prediction.sample_size} days")
            print(f"   Reason: {pick.reason}")


if __name__ == "__main__":
    main()
