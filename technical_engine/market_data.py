"""Market data collection via yfinance (Step 5)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from config.settings import get_settings
from data.db import OHLCV, get_db_session

logger = logging.getLogger(__name__)

INTERVALS = {
    "1d": {"period": "2y", "interval": "1d"},
    "1h": {"period": "60d", "interval": "1h"},
    "15m": {"period": "30d", "interval": "15m"},
}

INDEX_SYMBOLS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}


def to_yfinance_symbol(symbol: str) -> str:
    symbol = symbol.upper().strip()
    if symbol.startswith("^"):
        return symbol
    if symbol in INDEX_SYMBOLS:
        return INDEX_SYMBOLS[symbol]
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        return f"{symbol}.NS"
    return symbol


def fetch_ohlcv(
    symbol: str,
    interval_key: str = "1d",
) -> Optional[pd.DataFrame]:
    yf_symbol = to_yfinance_symbol(symbol)
    cfg = INTERVALS.get(interval_key, INTERVALS["1d"])
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=cfg["period"], interval=cfg["interval"])
        if df is None or df.empty:
            return None
        df = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df[["open", "high", "low", "close", "volume"]]
    except Exception as exc:
        logger.warning("yfinance fetch failed for %s: %s", symbol, exc)
        return None


def cache_ohlcv(
    symbol: str,
    df: pd.DataFrame,
    interval_key: str,
    session: Session,
) -> int:
    base_symbol = symbol.upper().replace(".NS", "").replace(".BO", "")
    count = 0
    session.query(OHLCV).filter(
        OHLCV.symbol == base_symbol,
        OHLCV.interval == interval_key,
    ).delete()
    for ts, row in df.iterrows():
        session.add(
            OHLCV(
                symbol=base_symbol,
                interval=interval_key,
                timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0) or 0),
            )
        )
        count += 1
    return count


def load_ohlcv_from_db(
    symbol: str,
    interval_key: str = "1d",
    session: Optional[Session] = None,
) -> Optional[pd.DataFrame]:
    base_symbol = symbol.upper().replace(".NS", "").replace(".BO", "")

    def _load(sess: Session) -> Optional[pd.DataFrame]:
        rows = (
            sess.query(OHLCV)
            .filter(OHLCV.symbol == base_symbol, OHLCV.interval == interval_key)
            .order_by(OHLCV.timestamp)
            .all()
        )
        if not rows:
            return None
        data = {
            "open": [r.open for r in rows],
            "high": [r.high for r in rows],
            "low": [r.low for r in rows],
            "close": [r.close for r in rows],
            "volume": [r.volume for r in rows],
        }
        index = pd.DatetimeIndex([r.timestamp for r in rows])
        return pd.DataFrame(data, index=index)

    if session is not None:
        return _load(session)

    with get_db_session() as sess:
        return _load(sess)


def fetch_and_cache(
    symbol: str,
    intervals: Optional[list[str]] = None,
    session: Optional[Session] = None,
) -> dict[str, pd.DataFrame]:
    intervals = intervals or ["1d", "1h"]
    result: dict[str, pd.DataFrame] = {}

    def _fetch(sess: Session) -> dict[str, pd.DataFrame]:
        for interval_key in intervals:
            df = fetch_ohlcv(symbol, interval_key)
            if df is not None and not df.empty:
                cache_ohlcv(symbol, df, interval_key, sess)
                result[interval_key] = df
            elif interval_key != "1d":
                logger.debug("Falling back to daily for %s", symbol)
        if "1d" not in result:
            df = fetch_ohlcv(symbol, "1d")
            if df is not None and not df.empty:
                cache_ohlcv(symbol, df, "1d", sess)
                result["1d"] = df
        return result

    if session is not None:
        return _fetch(session)

    with get_db_session() as sess:
        return _fetch(sess)


def get_latest_price(symbol: str) -> Optional[float]:
    df = fetch_ohlcv(symbol, "1d")
    if df is not None and not df.empty:
        return float(df["close"].iloc[-1])
    return None


def get_index_trend(index_name: str = "NIFTY") -> str:
    df = fetch_ohlcv(index_name, "1d")
    if df is None or len(df) < 20:
        return "Unknown"
    recent = df["close"].iloc[-1]
    sma20 = df["close"].rolling(20).mean().iloc[-1]
    if recent > sma20 * 1.01:
        return "Bullish"
    if recent < sma20 * 0.99:
        return "Bearish"
    return "Neutral"


def get_avg_volume(symbol: str, days: int = 20) -> float:
    df = load_ohlcv_from_db(symbol, "1d")
    if df is None:
        df = fetch_ohlcv(symbol, "1d")
    if df is None or df.empty:
        return 0.0
    return float(df["volume"].tail(days).mean())
