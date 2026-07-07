from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

MARKETS = {
    "US": {
        "timezone": "America/New_York",
        "open": time(9, 30),
        "close": time(16, 0),
        "square_off": time(15, 45),
    },
    "NSE": {
        "timezone": "Asia/Kolkata",
        "open": time(9, 15),
        "close": time(15, 30),
        "square_off": time(15, 15),
    },
}


def _now_in_market(market: str) -> datetime:
    tz = ZoneInfo(MARKETS[market]["timezone"])
    return datetime.now(tz)


def is_pre_market_window(market: str) -> bool:
    """NSE pre-open session: 9:00–9:15 AM IST."""
    now = _now_in_market(market)
    if now.weekday() >= 5:
        return False
    return time(9, 0) <= now.time() < time(9, 15)


def is_market_open(market: str) -> bool:
    """True during regular trading hours on weekdays."""
    now = _now_in_market(market)
    if now.weekday() >= 5:
        return False
    cfg = MARKETS[market]
    return cfg["open"] <= now.time() < cfg["close"]


def is_square_off_time(market: str) -> bool:
    """True when intraday positions must be closed before market close."""
    now = _now_in_market(market)
    if now.weekday() >= 5:
        return False
    cfg = MARKETS[market]
    return cfg["square_off"] <= now.time() < cfg["close"]


def is_exit_window(market: str, minutes_before_close: int = 60) -> bool:
    """True when we should exit all positions (default: 1 hour before NSE close)."""
    now = _now_in_market(market)
    if now.weekday() >= 5:
        return False
    cfg = MARKETS[market]
    close_dt = datetime.combine(now.date(), cfg["close"], tzinfo=now.tzinfo)
    exit_start = close_dt - timedelta(minutes=minutes_before_close)
    return exit_start.time() <= now.time() < cfg["close"]


def minutes_to_close(market: str) -> int:
    now = _now_in_market(market)
    if now.weekday() >= 5 or not is_market_open(market):
        return 0
    cfg = MARKETS[market]
    close_dt = datetime.combine(now.date(), cfg["close"], tzinfo=now.tzinfo)
    return max(0, int((close_dt - now).total_seconds() / 60))


def market_status(market: str) -> str:
    now = _now_in_market(market)
    if now.weekday() >= 5:
        return "Closed (weekend)"
    if is_exit_window(market):
        return f"Exit window ({minutes_to_close(market)} min to close)"
    if is_square_off_time(market):
        return "Square-off window (close positions)"
    if is_market_open(market):
        return f"Open ({minutes_to_close(market)} min to close)"
    return "Closed"
