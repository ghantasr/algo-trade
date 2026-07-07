"""
Indian intraday broker fee calculator (Zerodha-style approximation).

Fees vary by broker — adjust in .env if needed.
"""


def buy_side_fees(buy_price: float, quantity: int, flat_brokerage: float = 20.0) -> float:
    buy_value = buy_price * quantity
    brokerage = min(buy_value * 0.0003, flat_brokerage)
    exchange = buy_value * 0.0000345
    sebi = buy_value * 0.0000001
    stamp = buy_value * 0.00003
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + exchange + sebi + stamp + gst


def sell_side_fees(sell_price: float, quantity: int, flat_brokerage: float = 20.0) -> float:
    sell_value = sell_price * quantity
    brokerage = min(sell_value * 0.0003, flat_brokerage)
    stt = sell_value * 0.00025
    exchange = sell_value * 0.0000345
    sebi = sell_value * 0.0000001
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + stt + exchange + sebi + gst


def round_trip_fees(buy_price: float, sell_price: float, quantity: int) -> float:
    return buy_side_fees(buy_price, quantity) + sell_side_fees(sell_price, quantity)


def break_even_pct(buy_price: float, quantity: int) -> float:
    """Minimum % gain on buy value to break even (sell at same price as buy)."""
    buy_value = buy_price * quantity
    if buy_value <= 0:
        return 0.0
    fees = buy_side_fees(buy_price, quantity) + sell_side_fees(buy_price, quantity)
    return (fees / buy_value) * 100


def net_pnl(buy_price: float, sell_price: float, quantity: int) -> dict:
    """Calculate gross and net P&L after Indian intraday fees."""
    buy_value = buy_price * quantity
    sell_value = sell_price * quantity
    gross = sell_value - buy_value
    fees = round_trip_fees(buy_price, sell_price, quantity)
    net = gross - fees
    net_pct = (net / buy_value * 100) if buy_value > 0 else 0.0

    return {
        "buy_value": buy_value,
        "sell_value": sell_value,
        "gross_pnl": gross,
        "fees": fees,
        "net_pnl": net,
        "net_pct": net_pct,
    }
