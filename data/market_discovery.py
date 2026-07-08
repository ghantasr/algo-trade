"""
Fetch live market data from NSE India and financial sites.

No static watchlist — discovers top movers dynamically.
"""

import json
import re
import time
from dataclasses import dataclass
from typing import List, Optional

import requests
import yfinance as yf

from data.nifty_symbols import NIFTY_50, to_yahoo
from utils.logger import logger

NSE_HOME = "https://www.nseindia.com"
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/top-gainers-losers",
}


@dataclass
class DiscoveredStock:
    symbol: str          # Yahoo format: RELIANCE.NS
    name: str
    price: float
    change_pct: float    # % change today
    volume: float
    source: str          # nse_gainers | nse_preopen | yfinance_scan
    score: float = 0.0


def _nse_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    session.get(NSE_HOME, timeout=10)
    time.sleep(0.5)
    return session


def _parse_nse_items(items: list) -> List[DiscoveredStock]:
    results = []
    for item in items:
        symbol_raw = item.get("symbol", "")
        if not symbol_raw:
            continue
        pct = float(item.get("net_price", item.get("pChange", item.get("perChange", 0))) or 0)
        ltp = float(item.get("ltp", item.get("lastPrice", 0)) or 0)
        vol = float(item.get("trade_quantity", item.get("tradedVolume", 0)) or 0)
        results.append(DiscoveredStock(
            symbol=to_yahoo(symbol_raw),
            name=symbol_raw,
            price=ltp,
            change_pct=pct,
            volume=vol,
            source="nse_gainers",
            score=pct,
        ))
    return results


def fetch_nse_gainers(limit: int = 20) -> List[DiscoveredStock]:
    """Top gainers from NSE India website."""
    results = []
    try:
        session = _nse_session()
        url = f"{NSE_HOME}/api/live-analysis-variations?index=gainers"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # NSE returns {NIFTY: {data: [...]}, BANKNIFTY: {data: [...]}, ...}
        all_items = []
        for key in ("NIFTY", "BANKNIFTY", "NIFTYNEXT50", "allSec", "SecGtr20"):
            section = data.get(key, {})
            if isinstance(section, dict):
                all_items.extend(section.get("data", []))

        parsed = _parse_nse_items(all_items)
        parsed.sort(key=lambda s: s.change_pct, reverse=True)
        results = parsed[:limit]
        logger.info("NSE gainers: fetched %d stocks", len(results))
    except Exception as e:
        logger.warning("NSE gainers fetch failed: %s", e)
    return results


def fetch_nse_most_active(limit: int = 20) -> List[DiscoveredStock]:
    """Most active stocks by volume from NSE gainers endpoint (sorted by volume)."""
    results = []
    try:
        session = _nse_session()
        url = f"{NSE_HOME}/api/live-analysis-variations?index=gainers"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        all_items = []
        for key in data:
            if key == "legends":
                continue
            section = data.get(key, {})
            if isinstance(section, dict):
                all_items.extend(section.get("data", []))

        parsed = _parse_nse_items(all_items)
        for s in parsed:
            s.source = "nse_most_active"
            s.score = s.volume / 1_000_000 + max(s.change_pct, 0)
        parsed.sort(key=lambda s: s.volume, reverse=True)
        results = parsed[:limit]
        logger.info("NSE most active: fetched %d stocks", len(results))
    except Exception as e:
        logger.warning("NSE most active fetch failed: %s", e)
    return results


def fetch_nse_preopen(limit: int = 20) -> List[DiscoveredStock]:
    """Pre-open market data (9:00–9:15 AM IST) — gap up candidates."""
    results = []
    try:
        session = _nse_session()
        url = f"{NSE_HOME}/api/market-data-pre-open?key=NIFTY"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", [])
        for item in items:
            meta = item.get("metadata", item)
            symbol_raw = meta.get("symbol", "")
            if not symbol_raw:
                continue
            pct = float(meta.get("pChange", meta.get("change", 0)) or 0)
            ltp = float(meta.get("lastPrice", meta.get("iep", 0)) or 0)
            results.append(DiscoveredStock(
                symbol=to_yahoo(symbol_raw),
                name=symbol_raw,
                price=ltp,
                change_pct=pct,
                volume=0,
                source="nse_preopen",
                score=pct * 2,
            ))

        results.sort(key=lambda s: s.change_pct, reverse=True)
        results = results[:limit]
        logger.info("NSE pre-open: fetched %d stocks", len(results))
    except Exception as e:
        logger.warning("NSE pre-open fetch failed: %s", e)
    return results


def fetch_moneycontrol_gainers(limit: int = 15) -> List[DiscoveredStock]:
    """Scrape top NSE gainers from Moneycontrol (fallback source)."""
    results = []
    try:
        url = "https://www.moneycontrol.com/stocks/marketstats/nsegainer/index.php"
        headers = {"User-Agent": NSE_HEADERS["User-Agent"]}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        rows = re.findall(
            r'target="_blank"\s*title="([^"]+)"[^>]*>\s*([A-Z0-9&amp;-]+)\s*<',
            resp.text,
        )
        pct_matches = re.findall(r'([+-]?\d+\.\d+)%', resp.text)

        seen = set()
        pct_idx = 0
        for _title, symbol_raw in rows:
            symbol_raw = symbol_raw.replace("&amp;", "&").strip()
            if symbol_raw in seen or len(symbol_raw) < 2:
                continue
            seen.add(symbol_raw)
            pct = float(pct_matches[pct_idx]) if pct_idx < len(pct_matches) else 0
            pct_idx += 1
            if pct <= 0:
                continue
            results.append(DiscoveredStock(
                symbol=to_yahoo(symbol_raw),
                name=symbol_raw,
                price=0,
                change_pct=pct,
                volume=0,
                source="moneycontrol",
                score=pct,
            ))
            if len(results) >= limit:
                break

        logger.info("Moneycontrol gainers: fetched %d stocks", len(results))
    except Exception as e:
        logger.warning("Moneycontrol scrape failed: %s", e)
    return results


def scan_nifty_momentum(limit: int = 15) -> List[DiscoveredStock]:
    """
    Fallback: scan all NIFTY 50 stocks via Yahoo Finance,
    rank by today's % gain + volume.
    """
    results = []
    symbols = [to_yahoo(s) for s in NIFTY_50]

    try:
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                ticker = tickers.tickers.get(sym) or yf.Ticker(sym)
                info = ticker.history(period="2d", interval="5m")
                if info.empty or len(info) < 5:
                    continue

                today = info[info.index.date == info.index[-1].date()]
                if today.empty:
                    continue

                open_price = float(today["Open"].iloc[0])
                current = float(today["Close"].iloc[-1])
                volume = float(today["Volume"].sum())
                if open_price <= 0:
                    continue

                pct = ((current - open_price) / open_price) * 100
                if pct <= 0.3:
                    continue

                results.append(DiscoveredStock(
                    symbol=sym,
                    name=sym.replace(".NS", ""),
                    price=current,
                    change_pct=round(pct, 2),
                    volume=volume,
                    source="yfinance_scan",
                    score=pct + min(volume / 1_000_000, 5),
                ))
            except Exception:
                continue

        results.sort(key=lambda s: s.score, reverse=True)
        results = results[:limit]
        logger.info("YFinance NIFTY scan: found %d momentum stocks", len(results))
    except Exception as e:
        logger.warning("YFinance NIFTY scan failed: %s", e)
    return results


def discover_market_stocks(pre_market: bool = False, limit: int = 20) -> List[DiscoveredStock]:
    """
    Hit multiple financial sources and merge into one ranked list.
    Called before market open AND during the day.
    """
    all_stocks: dict = {}

    sources = []
    if pre_market:
        sources = [fetch_nse_preopen, fetch_nse_gainers, fetch_moneycontrol_gainers]
    else:
        sources = [fetch_nse_gainers, fetch_nse_most_active, fetch_moneycontrol_gainers]

    for fetch_fn in sources:
        for stock in fetch_fn(limit=limit):
            key = stock.symbol
            if key not in all_stocks or stock.score > all_stocks[key].score:
                all_stocks[key] = stock

    if len(all_stocks) < 5:
        logger.info("Live sources returned few results — scanning NIFTY 50")
        for stock in scan_nifty_momentum(limit=limit):
            key = stock.symbol
            if key not in all_stocks:
                all_stocks[key] = stock

    ranked = sorted(all_stocks.values(), key=lambda s: s.score, reverse=True)
    return ranked[:limit]


def save_daily_candidates(stocks: List[DiscoveredStock], filepath: str):
    import os
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    data = [
        {
            "symbol": s.symbol,
            "name": s.name,
            "price": s.price,
            "change_pct": s.change_pct,
            "source": s.source,
            "score": s.score,
        }
        for s in stocks
    ]
    with open(filepath, "w") as f:
        json.dump({"stocks": data, "updated": time.time()}, f, indent=2)


def load_daily_candidates(filepath: str) -> List[str]:
    import os
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        return [s["symbol"] for s in data.get("stocks", [])]
    except Exception:
        return []
