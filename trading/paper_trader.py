from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from utils.logger import logger


@dataclass
class Trade:
    action: str  # "BUY" or "SELL"
    symbol: str
    price: float
    quantity: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Portfolio:
    cash: float
    shares: float = 0.0
    trades: List[Trade] = field(default_factory=list)

    @property
    def total_value(self) -> float:
        return self.cash  # Updated with current price when reporting

    def value_at_price(self, price: float) -> float:
        return self.cash + (self.shares * price)


class PaperTrader:
    """Simulates trades with fake money — safe for learning."""

    def __init__(self, starting_balance: float):
        self.portfolio = Portfolio(cash=starting_balance)

    def buy(self, symbol: str, price: float, amount_to_spend: Optional[float] = None) -> Optional[Trade]:
        spend = amount_to_spend or self.portfolio.cash
        if spend <= 0 or self.portfolio.cash < spend:
            logger.warning("Not enough cash to buy. Cash: %.2f", self.portfolio.cash)
            return None

        quantity = spend / price
        self.portfolio.cash -= spend
        self.portfolio.shares += quantity

        trade = Trade(action="BUY", symbol=symbol, price=price, quantity=quantity)
        self.portfolio.trades.append(trade)
        logger.info("BUY %.4f shares of %s at $%.2f", quantity, symbol, price)
        return trade

    def sell(self, symbol: str, price: float, quantity: Optional[float] = None) -> Optional[Trade]:
        sell_qty = quantity or self.portfolio.shares
        if sell_qty <= 0 or self.portfolio.shares < sell_qty:
            logger.warning("No shares to sell. Shares held: %.4f", self.portfolio.shares)
            return None

        proceeds = sell_qty * price
        self.portfolio.cash += proceeds
        self.portfolio.shares -= sell_qty

        trade = Trade(action="SELL", symbol=symbol, price=price, quantity=sell_qty)
        self.portfolio.trades.append(trade)
        logger.info("SELL %.4f shares of %s at $%.2f", sell_qty, symbol, price)
        return trade

    def status(self, current_price: float) -> str:
        total = self.portfolio.value_at_price(current_price)
        return (
            f"💰 Cash: ${self.portfolio.cash:,.2f}\n"
            f"📈 Shares: {self.portfolio.shares:.4f}\n"
            f"💵 Current price: ${current_price:,.2f}\n"
            f"📊 Portfolio value: ${total:,.2f}\n"
            f"🔄 Total trades: {len(self.portfolio.trades)}"
        )
