from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from config.settings import MAX_PROFIT_PCT, STOP_LOSS_PCT, TARGET_PROFIT_PCT
from strategies.momentum_scanner import get_current_price, is_falling
from trading.bucket import Position, display_symbol
from trading.fees import net_pnl


class SellReason(Enum):
    STOP_LOSS = "STOP_LOSS"
    TARGET_HIT = "TARGET_HIT"
    MAX_PROFIT = "MAX_PROFIT"
    FALLING = "FALLING"
    EOD_EXIT = "EOD_EXIT"


@dataclass
class SellAlert:
    position: Position
    current_price: float
    reason: SellReason
    message: str
    net_pnl: float
    net_pct: float


def evaluate_position(
    position: Position,
    force_eod: bool = False,
) -> Optional[SellAlert]:
    """Sell when falling, unprofitable after fees, or target hit."""
    price = get_current_price(position.symbol)
    if price is None:
        return None

    pnl = net_pnl(position.buy_price, price, position.quantity)
    name = display_symbol(position.symbol)

    if force_eod:
        return SellAlert(
            position=position,
            current_price=price,
            reason=SellReason.EOD_EXIT,
            net_pnl=pnl["net_pnl"],
            net_pct=pnl["net_pct"],
            message=_format_sell(name, position, price, pnl, SellReason.EOD_EXIT, ""),
        )

    # Priority 1: Stock is falling — exit before loss grows
    falling, fall_reason, drop = is_falling(position.symbol, position.buy_price)
    if falling:
        return SellAlert(
            position=position,
            current_price=price,
            reason=SellReason.FALLING,
            net_pnl=pnl["net_pnl"],
            net_pct=pnl["net_pct"],
            message=_format_sell(name, position, price, pnl, SellReason.FALLING, fall_reason),
        )

    # Priority 2: Stop loss after fees
    if pnl["net_pct"] <= -STOP_LOSS_PCT:
        return SellAlert(
            position=position,
            current_price=price,
            reason=SellReason.STOP_LOSS,
            net_pnl=pnl["net_pnl"],
            net_pct=pnl["net_pct"],
            message=_format_sell(name, position, price, pnl, SellReason.STOP_LOSS, "loss exceeded limit"),
        )

    # Priority 3: Profit targets after fees
    if pnl["net_pct"] >= MAX_PROFIT_PCT:
        return SellAlert(
            position=position,
            current_price=price,
            reason=SellReason.MAX_PROFIT,
            net_pnl=pnl["net_pnl"],
            net_pct=pnl["net_pct"],
            message=_format_sell(name, position, price, pnl, SellReason.MAX_PROFIT, "10%+ profit booked"),
        )

    if pnl["net_pct"] >= TARGET_PROFIT_PCT:
        return SellAlert(
            position=position,
            current_price=price,
            reason=SellReason.TARGET_HIT,
            net_pnl=pnl["net_pnl"],
            net_pct=pnl["net_pct"],
            message=_format_sell(name, position, price, pnl, SellReason.TARGET_HIT, "5%+ profit after fees"),
        )

    # Priority 4: Was profitable but now dropping toward break-even
    if pnl["net_pct"] < 0.5 and drop >= 0.8:
        return SellAlert(
            position=position,
            current_price=price,
            reason=SellReason.FALLING,
            net_pnl=pnl["net_pnl"],
            net_pct=pnl["net_pct"],
            message=_format_sell(
                name, position, price, pnl, SellReason.FALLING,
                f"profit fading — down {drop:.1f}% from high, near break-even",
            ),
        )

    return None


def evaluate_all(positions: List[Position], force_eod: bool = False) -> List[SellAlert]:
    alerts = []
    for pos in positions:
        alert = evaluate_position(pos, force_eod=force_eod)
        if alert:
            alerts.append(alert)
    return alerts


def format_bucket_status(positions: List[Position]) -> str:
    if not positions:
        return "🪣 *Your bucket is empty.*\n\nScanning NSE for momentum stocks..."

    lines = ["🪣 *Your Bucket*\n"]
    total_invested = 0.0
    total_net = 0.0

    for pos in positions:
        price = get_current_price(pos.symbol) or pos.buy_price
        pnl = net_pnl(pos.buy_price, price, pos.quantity)
        name = display_symbol(pos.symbol)
        emoji = "🟢" if pnl["net_pct"] >= 0 else "🔴"
        falling, fall_reason, _ = is_falling(pos.symbol, pos.buy_price)
        trend = f" ⚠️ {fall_reason}" if falling else ""

        lines.append(
            f"{emoji} *{name}* — {pos.quantity} shares{trend}\n"
            f"   Entry: ₹{pos.buy_price:,.2f} → Now: ₹{price:,.2f}\n"
            f"   Net P&L: ₹{pnl['net_pnl']:+,.0f} ({pnl['net_pct']:+.2f}% after fees)\n"
        )
        total_invested += pnl["buy_value"]
        total_net += pnl["net_pnl"]

    total_pct = (total_net / total_invested * 100) if total_invested > 0 else 0
    lines.append(
        f"📊 *Total invested:* ₹{total_invested:,.0f}\n"
        f"📊 *Total net P&L:* ₹{total_net:+,.0f} ({total_pct:+.2f}% after fees)"
    )
    return "\n".join(lines)


def _format_sell(name, position, price, pnl, reason: SellReason, detail: str) -> str:
    reason_text = {
        SellReason.STOP_LOSS: "⚠️ Stop loss — cut the loss before it grows",
        SellReason.TARGET_HIT: "✅ Target hit — 5%+ profit after fees!",
        SellReason.MAX_PROFIT: "🎉 10%+ profit — book it now!",
        SellReason.FALLING: f"📉 Stock falling — {detail}",
        SellReason.EOD_EXIT: "⏰ End of day — exit before 3:30 PM!",
    }[reason]

    return (
        f"🔴 *SELL Alert — {name}*\n\n"
        f"Entry: ₹{position.buy_price:,.2f} × {position.quantity}\n"
        f"Now: ₹{price:,.2f}\n"
        f"Net P&L: ₹{pnl['net_pnl']:+,.0f} ({pnl['net_pct']:+.2f}% after fees)\n"
        f"Fees: ₹{pnl['fees']:.0f}\n\n"
        f"{reason_text}\n\n"
        f"👉 Sell on broker, then:\n"
        f"`/sold {name} {position.quantity} {price:.2f}`"
    )
