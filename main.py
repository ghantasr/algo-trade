import threading
import time

from bot.telegram_handler import TelegramBot, send_message_sync
from config.settings import (
    CANDIDATES_FILE,
    CHECK_INTERVAL,
    EXIT_MINUTES_BEFORE_CLOSE,
    INTERVAL,
    INVESTMENT_PER_TRADE,
    MARKET,
    MAX_BUY_SUGGESTIONS,
    MAX_POSITIONS,
    PORTFOLIO_FILE,
    TARGET_PROFIT_PCT,
)
from data.market_discovery import discover_market_stocks, save_daily_candidates
from strategies.exit_advisor import evaluate_all, format_bucket_status
from strategies.momentum_scanner import (
    format_buy_recommendation,
    format_discovery_summary,
    scan_momentum_buys,
)
from strategies.premarket_analyzer import (
    analyze_premarket_stocks,
    format_premarket_report,
)
from config.settings import PREMARKET_ONLY
from trading.bucket import Bucket, display_symbol, normalize_symbol
from trading.fees import net_pnl
from utils.logger import logger
from utils.market_hours import (
    is_exit_window,
    is_market_open,
    is_pre_market_window,
    market_status,
    minutes_to_close,
)


class AlgoTradeApp:
    """
    NSE intraday advisor — NO fixed watchlist.

    1. Before market: hits NSE / Moneycontrol → finds top movers
    2. During market: picks stocks already going UP → suggests BUY
    3. Monitors your bucket → suggests SELL when falling or target hit
    4. 1 hour before close → exit everything
    """

    def __init__(self):
        self.bucket = Bucket(PORTFOLIO_FILE)
        self.is_running = False
        self.eod_alert_sent = False
        self.pre_market_done = False
        self.last_suggested: set = set()
        self.telegram = TelegramBot(
            on_bought=self.handle_bought,
            on_sold=self.handle_sold,
            on_bucket=self.get_bucket_status,
            on_scan=self.run_scan_now,
            on_start=self.start_scanning,
            on_stop=self.stop_scanning,
        )

    def start_scanning(self):
        self.is_running = True
        self.eod_alert_sent = False
        logger.info("Scanning enabled")

    def stop_scanning(self):
        self.is_running = False
        logger.info("Scanning disabled")

    def get_bucket_status(self) -> str:
        return format_bucket_status(self.bucket.all_positions())

    def handle_bought(self, symbol: str, quantity: int, price: float) -> str:
        pos = self.bucket.add(symbol, quantity, price)
        name = display_symbol(pos.symbol)
        investment = price * quantity
        return (
            f"✅ *Added to bucket*\n\n"
            f"*{name}* — {quantity} shares @ ₹{price:,.2f}\n"
            f"Invested: ₹{investment:,.0f}\n"
            f"Target: +{TARGET_PROFIT_PCT}% after fees\n\n"
            f"I'll alert you when it starts falling or hits target."
        )

    def handle_sold(self, symbol: str, quantity: int, price: float) -> str:
        norm = normalize_symbol(symbol)
        pos = self.bucket.get(norm)
        if not pos:
            return f"❌ {display_symbol(norm)} not in your bucket."

        buy_price = pos.buy_price
        pnl = net_pnl(buy_price, price, quantity)
        self.bucket.remove(symbol, quantity)
        name = display_symbol(norm)
        self.last_suggested.discard(norm)

        emoji = "🎉" if pnl["net_pct"] >= TARGET_PROFIT_PCT else "📤"
        return (
            f"{emoji} *Sold & removed from bucket*\n\n"
            f"*{name}* — {quantity} shares @ ₹{price:,.2f}\n"
            f"Entry was: ₹{buy_price:,.2f}\n"
            f"Net P&L: ₹{pnl['net_pnl']:+,.0f} ({pnl['net_pct']:+.2f}% after fees)\n"
            f"Fees paid: ₹{pnl['fees']:.0f}"
        )

    def run_scan_now(self) -> str:
        pre = is_pre_market_window(MARKET)
        if not is_market_open(MARKET) and not pre:
            return f"Market is closed. Status: {market_status(MARKET)}"

        held = [p.symbol for p in self.bucket.all_positions()]
        if not self.bucket.has_room(MAX_POSITIONS):
            return self.get_bucket_status() + "\n\n⚠️ Bucket full — sell first."

        candidates, discovered = scan_momentum_buys(
            held, INTERVAL, MAX_BUY_SUGGESTIONS, pre_market=pre,
        )
        save_daily_candidates(discovered, CANDIDATES_FILE)

        lines = [format_discovery_summary(discovered, pre_market=pre), ""]
        if not candidates:
            lines.append("No stocks passing momentum + fee checks right now.")
        else:
            for c in candidates:
                lines.append(format_buy_recommendation(c))
                lines.append("")
        return "\n".join(lines)

    def _run_pre_market_scan(self):
        logger.info("Running pre-market discovery scan")
        send_message_sync("🌅 *Pre-market scan starting...*\nFetching NSE pre-open & top gainers...")

        # Discover stocks from NSE pre-open / gainers
        discovered = discover_market_stocks(pre_market=True, limit=25)
        save_daily_candidates(discovered, CANDIDATES_FILE)

        # Run the new pre-market analyzer with profit predictions
        send_message_sync("📊 Analysing historical data for profit predictions...")
        picks = analyze_premarket_stocks(discovered, max_results=MAX_BUY_SUGGESTIONS)

        # Send the comprehensive pre-market report
        report = format_premarket_report(picks)
        send_message_sync(report)

        # Also send the raw discovery summary for transparency
        send_message_sync(format_discovery_summary(discovered, pre_market=True))

        self.pre_market_done = True

    def _check_sells(self, force_eod: bool = False):
        positions = self.bucket.all_positions()
        if not positions:
            return
        alerts = evaluate_all(positions, force_eod=force_eod)
        for alert in alerts:
            send_message_sync(alert.message)

    def _check_buys(self):
        if not self.bucket.has_room(MAX_POSITIONS):
            return

        held = [p.symbol for p in self.bucket.all_positions()]
        candidates, discovered = scan_momentum_buys(
            held, INTERVAL, MAX_BUY_SUGGESTIONS, pre_market=False,
        )
        save_daily_candidates(discovered, CANDIDATES_FILE)

        for c in candidates:
            if c.symbol in self.last_suggested:
                continue
            self.last_suggested.add(c.symbol)
            send_message_sync(format_buy_recommendation(c))

    def _send_eod_summary(self):
        positions = self.bucket.all_positions()
        if not positions:
            send_message_sync(
                f"⏰ *Market closes in {minutes_to_close(MARKET)} min*\n\n"
                f"Bucket empty — no positions to exit."
            )
            return

        status = format_bucket_status(positions)
        send_message_sync(
            f"⏰ *EXIT ALL — {minutes_to_close(MARKET)} min to close*\n\n"
            f"{status}\n\n"
            f"Sell everything on broker:\n"
            f"`/sold SYMBOL QTY PRICE`"
        )
        self._check_sells(force_eod=True)

    def advisory_loop(self):
        logger.info("Advisory loop started (dynamic NSE discovery)")

        # Skip startup broadcast on GitHub Actions (bot restarts every 2h)
        # to avoid spamming users. Only broadcast on first run of the day.
        import os as _os
        if not _os.getenv("GITHUB_ACTIONS"):
            send_message_sync(
                f"🇮🇳 *NSE Momentum Advisor Online*\n\n"
                f"No fixed watchlist — I scan NSE / Moneycontrol live\n"
                f"Investment per trade: ₹{INVESTMENT_PER_TRADE:,.0f}\n"
                f"Target: 5–10% profit after broker fees\n"
                f"Exit: {EXIT_MINUTES_BEFORE_CLOSE} min before 3:30 PM\n\n"
                f"/run — start scanning\n"
                f"/scan — scan now\n"
                f"/help — commands"
            )
        else:
            logger.info("Skipping startup broadcast (GitHub Actions — frequent restart)")

        while True:
            if self.is_running:
                try:
                    # Pre-market scan: 9:00–9:15 AM IST (once per day)
                    if is_pre_market_window(MARKET) and not self.pre_market_done:
                        self._run_pre_market_scan()

                    if is_market_open(MARKET):
                        if is_exit_window(MARKET, EXIT_MINUTES_BEFORE_CLOSE):
                            if not self.eod_alert_sent:
                                self._send_eod_summary()
                                self.eod_alert_sent = True
                            else:
                                self._check_sells(force_eod=True)
                        else:
                            self.eod_alert_sent = False
                            self._check_sells(force_eod=False)
                            # Live scanning is optional — skip if PREMARKET_ONLY
                            if not PREMARKET_ONLY:
                                self._check_buys()

                    # Reset pre-market flag at midnight next day
                    if not is_pre_market_window(MARKET) and not is_market_open(MARKET):
                        from utils.market_hours import _now_in_market
                        now = _now_in_market(MARKET)
                        if now.hour < 9:
                            self.pre_market_done = False
                            self.last_suggested.clear()

                except Exception as e:
                    logger.error("Advisory error: %s", e)
                    send_message_sync(f"⚠️ Error: {e}")

            time.sleep(CHECK_INTERVAL)

    def start(self):
        thread = threading.Thread(target=self.advisory_loop, daemon=True)
        thread.start()
        self.telegram.run_polling()


if __name__ == "__main__":
    app = AlgoTradeApp()
    app.start()
