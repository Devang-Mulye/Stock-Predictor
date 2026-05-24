"""Signal generation engine (Steps 7 & 20)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from sqlalchemy.orm import Session

from config.settings import get_settings
from data.db import ArticleTicker, NewsArticle, Signal, get_db_session
from technical_engine.indicators import compute_indicators
from technical_engine.market_data import (
    fetch_and_cache,
    get_index_trend,
    load_ohlcv_from_db,
)

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    WATCHLIST = "WATCHLIST"


@dataclass
class GeneratedSignal:
    symbol: str
    signal_type: SignalType
    confidence: float
    reasons: list[str]
    indicators: dict[str, Any]
    sentiment_score: Optional[float] = None
    sector_momentum: Optional[str] = None


def _get_sector(symbol: str) -> str:
    import json
    from pathlib import Path

    path = get_settings().project_root / "data" / "ticker_aliases.json"
    with open(path, encoding="utf-8") as f:
        aliases = json.load(f)
    return aliases.get(symbol, {}).get("sector", "Unknown")


def _aggregate_news_sentiment(
    symbol: str,
    session: Session,
) -> tuple[Optional[float], list[str]]:
    rows = (
        session.query(NewsArticle)
        .join(ArticleTicker, ArticleTicker.article_id == NewsArticle.id)
        .filter(ArticleTicker.ticker == symbol)
        .filter(NewsArticle.sentiment_label.isnot(None))
        .order_by(NewsArticle.created_at.desc())
        .limit(10)
        .all()
    )
    if not rows:
        return None, []
    scores = [a.sentiment_score or 0 for a in rows]
    avg = sum(scores) / len(scores)
    reasons = [f"News sentiment avg {avg:.2f} from {len(rows)} articles"]
    return avg, reasons


def generate_signal(
    symbol: str,
    sentiment_score: Optional[float] = None,
    news_reasons: Optional[list[str]] = None,
    session: Optional[Session] = None,
) -> GeneratedSignal:
    settings = get_settings()
    news_reasons = news_reasons or []

    fetch_and_cache(symbol, ["1d"], session=session)
    df = load_ohlcv_from_db(symbol, "1d", session=session)
    if df is None or len(df) < 30:
        return GeneratedSignal(
            symbol=symbol,
            signal_type=SignalType.HOLD,
            confidence=0.0,
            reasons=["Insufficient market data"],
            indicators={},
        )

    indicators = compute_indicators(df)
    reasons: list[str] = list(news_reasons)
    score = 0.0

    rsi = indicators.get("rsi")
    macd_cross = indicators.get("macd_cross")
    volume_spike = indicators.get("volume_spike", False)
    breakout_up = indicators.get("breakout_up", False)
    close = indicators.get("close", 0)

    positive_news = sentiment_score is not None and sentiment_score > 0.2
    negative_news = sentiment_score is not None and sentiment_score < -0.2

    if positive_news:
        score += 25
        reasons.append("Positive news sentiment")
    if negative_news:
        score -= 25
        reasons.append("Negative news sentiment")

    if rsi is not None:
        if settings.rsi_buy_min <= rsi <= settings.rsi_buy_max:
            score += 20
            reasons.append(f"RSI in momentum zone ({rsi:.1f})")
        elif rsi > 80:
            score -= 15
            reasons.append(f"RSI overbought ({rsi:.1f})")
        elif rsi < 30:
            score -= 10
            reasons.append(f"RSI oversold ({rsi:.1f})")

    if macd_cross == "bullish":
        score += 20
        reasons.append("MACD bullish crossover")
    elif macd_cross == "bearish":
        score -= 20
        reasons.append("MACD bearish crossover")

    if volume_spike:
        score += 15
        reasons.append("Volume spike above 20-day average")

    if breakout_up:
        score += 15
        reasons.append("Price breakout detected")

    market_trend = get_index_trend("NIFTY")
    sector = _get_sector(symbol)
    if market_trend == "Bullish":
        score += 5
        reasons.append("NIFTY trend bullish")
    elif market_trend == "Bearish":
        score -= 5
        reasons.append("NIFTY trend bearish")

    if positive_news and volume_spike and macd_cross == "bullish":
        if rsi is not None and settings.rsi_buy_min <= rsi <= settings.rsi_buy_max:
            score += 10
            reasons.append("Swing strategy criteria met (news + momentum)")

    confidence = max(0.0, min(100.0, 50 + score))

    if score >= 35 and positive_news:
        signal_type = SignalType.BUY
    elif score <= -25 or negative_news:
        signal_type = SignalType.SELL
    elif score >= 15:
        signal_type = SignalType.WATCHLIST
    else:
        signal_type = SignalType.HOLD

    return GeneratedSignal(
        symbol=symbol,
        signal_type=signal_type,
        confidence=confidence,
        reasons=reasons,
        indicators=indicators,
        sentiment_score=sentiment_score,
        sector_momentum=sector,
    )


def _persist_signal(gen: GeneratedSignal, session: Session) -> Signal:
    record = Signal(
        symbol=gen.symbol,
        signal_type=gen.signal_type.value,
        confidence=gen.confidence,
        reasons=json.dumps(gen.reasons),
        sentiment_score=gen.sentiment_score,
        rsi=gen.indicators.get("rsi"),
        macd_signal=gen.indicators.get("macd_cross"),
        volume_spike=gen.indicators.get("volume_spike", False),
        sector_momentum=gen.sector_momentum,
        current_price=gen.indicators.get("close"),
    )
    session.add(record)
    session.flush()
    return record


def generate_signals_for_symbols(
    symbols: list[str],
    session: Optional[Session] = None,
) -> list[Signal]:
    results: list[Signal] = []

    def _run(sess: Session) -> list[Signal]:
        for symbol in symbols:
            sent, news_reasons = _aggregate_news_sentiment(symbol, sess)
            gen = generate_signal(symbol, sent, news_reasons, session=sess)
            if gen.signal_type != SignalType.HOLD:
                results.append(_persist_signal(gen, sess))
        return results

    if session is not None:
        return _run(session)

    with get_db_session() as sess:
        return _run(sess)


def get_tickers_from_recent_news(session: Session, limit: int = 30) -> list[str]:
    rows = (
        session.query(ArticleTicker.ticker)
        .order_by(ArticleTicker.created_at.desc())
        .limit(limit * 3)
        .all()
    )
    tickers: list[str] = []
    seen: set[str] = set()
    for (ticker,) in rows:
        if ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
        if len(tickers) >= limit:
            break
    settings = get_settings()
    combined = list(dict.fromkeys(tickers + settings.default_watchlist))
    return combined[:40]
