import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from utils.logger import logger


def normalize_symbol(symbol: str) -> str:
    """RELIANCE → RELIANCE.NS"""
    s = symbol.strip().upper()
    if not s.endswith(".NS") and not s.endswith(".BO"):
        s = f"{s}.NS"
    return s


def display_symbol(symbol: str) -> str:
    """RELIANCE.NS → RELIANCE"""
    return symbol.replace(".NS", "").replace(".BO", "")


@dataclass
class Position:
    symbol: str
    quantity: int
    buy_price: float
    bought_at: str = field(default_factory=lambda: datetime.now().isoformat())


class Bucket:
    """Tracks stocks YOU confirmed buying/selling via Telegram."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.positions: Dict[str, Position] = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
            for symbol, pos in data.get("positions", {}).items():
                self.positions[symbol] = Position(**pos)
            logger.info("Loaded %d positions from bucket", len(self.positions))
        except Exception as e:
            logger.error("Failed to load portfolio: %s", e)

    def _save(self):
        os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)
        data = {"positions": {k: asdict(v) for k, v in self.positions.items()}}
        with open(self.filepath, "w") as f:
            json.dump(data, f, indent=2)

    def add(self, symbol: str, quantity: int, buy_price: float) -> Position:
        symbol = normalize_symbol(symbol)
        if symbol in self.positions:
            existing = self.positions[symbol]
            total_qty = existing.quantity + quantity
            avg_price = (
                (existing.buy_price * existing.quantity) + (buy_price * quantity)
            ) / total_qty
            existing.quantity = total_qty
            existing.buy_price = avg_price
            self._save()
            return existing

        pos = Position(symbol=symbol, quantity=quantity, buy_price=buy_price)
        self.positions[symbol] = pos
        self._save()
        logger.info("Bucket + %s x%d @ ₹%.2f", symbol, quantity, buy_price)
        return pos

    def remove(self, symbol: str, quantity: int) -> Optional[Position]:
        symbol = normalize_symbol(symbol)
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]
        if quantity >= pos.quantity:
            del self.positions[symbol]
        else:
            pos.quantity -= quantity

        self._save()
        logger.info("Bucket - %s x%d", symbol, quantity)
        return pos

    def get(self, symbol: str) -> Optional[Position]:
        return self.positions.get(normalize_symbol(symbol))

    def all_positions(self) -> List[Position]:
        return list(self.positions.values())

    def count(self) -> int:
        return len(self.positions)

    def has_room(self, max_positions: int) -> bool:
        return self.count() < max_positions
