"""LLM reasoning layer via Ollama (Step 8)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from config.prompts import DISCLAIMER, MASTER_ANALYSIS_PROMPT
from config.settings import get_settings
from data.db import NewsArticle, Recommendation, Signal, get_db_session
from llm_engine.client import OllamaClient
from technical_engine.market_data import get_index_trend, get_latest_price

logger = logging.getLogger(__name__)


@dataclass
class ParsedRecommendation:
    recommendation: str
    confidence: float
    risk_level: str
    entry_price: Optional[float]
    stop_loss: Optional[float]
    target_price: Optional[float]
    holding_period: str
    reasoning: str


def _parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None


def parse_llm_response(text: str) -> ParsedRecommendation:
    fields = {
        "recommendation": "HOLD",
        "confidence": 50.0,
        "risk_level": "Medium",
        "entry_price": None,
        "stop_loss": None,
        "target_price": None,
        "holding_period": "3-10 trading days",
        "reasoning": text,
    }

    patterns = {
        "recommendation": r"Recommendation:\s*(\w+)",
        "confidence": r"Confidence:\s*([\d.]+)\s*%?",
        "risk_level": r"Risk Level:\s*(\w+)",
        "entry_price": r"Suggested Entry:\s*₹?\s*([\d,.]+)",
        "stop_loss": r"Suggested Stop Loss:\s*₹?\s*([\d,.]+)",
        "target_price": r"Suggested Target:\s*₹?\s*([\d,.]+)",
        "holding_period": r"Suggested Holding Period:\s*(.+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            if key == "confidence":
                fields[key] = float(val)
            elif key in ("entry_price", "stop_loss", "target_price"):
                fields[key] = _parse_price(val)
            else:
                fields[key] = val

    reasoning_match = re.search(r"Reasoning:\s*(.+)", text, re.DOTALL | re.IGNORECASE)
    if reasoning_match:
        fields["reasoning"] = reasoning_match.group(1).strip()

    return ParsedRecommendation(
        recommendation=fields["recommendation"].upper(),
        confidence=fields["confidence"],
        risk_level=fields["risk_level"],
        entry_price=fields["entry_price"],
        stop_loss=fields["stop_loss"],
        target_price=fields["target_price"],
        holding_period=fields["holding_period"],
        reasoning=fields["reasoning"],
    )


def _get_news_summary(symbol: str, session: Session) -> str:
    from data.db import ArticleTicker

    articles = (
        session.query(NewsArticle)
        .join(ArticleTicker, ArticleTicker.article_id == NewsArticle.id)
        .filter(ArticleTicker.ticker == symbol)
        .order_by(NewsArticle.created_at.desc())
        .limit(5)
        .all()
    )
    if not articles:
        return "No recent news available."
    lines = []
    for a in articles:
        sent = a.sentiment_label or "Unknown"
        lines.append(f"- {a.title} ({sent})")
    return "\n".join(lines)


def _format_technical_summary(signal: Signal) -> str:
    parts = []
    if signal.rsi is not None:
        parts.append(f"RSI: {signal.rsi:.1f}")
    if signal.macd_signal:
        parts.append(f"MACD: {signal.macd_signal}")
    if signal.volume_spike:
        parts.append("Volume: spike detected")
    if signal.current_price:
        parts.append(f"Price: ₹{signal.current_price:.2f}")
    return "\n".join(parts) if parts else "Limited technical data"


def build_prompt(symbol: str, signal: Signal, session: Session) -> str:
    import json
    from pathlib import Path

    path = get_settings().project_root / "data" / "ticker_aliases.json"
    with open(path, encoding="utf-8") as f:
        aliases = json.load(f)
    company = aliases.get(symbol, {}).get("company", symbol)

    price = signal.current_price or get_latest_price(symbol) or 0.0
    news = _get_news_summary(symbol, session)
    sentiment_label = "Positive" if (signal.sentiment_score or 0) > 0 else (
        "Negative" if (signal.sentiment_score or 0) < 0 else "Neutral"
    )

    return MASTER_ANALYSIS_PROMPT.format(
        symbol=symbol,
        company_name=company,
        news_summary=news,
        sentiment_label=sentiment_label,
        sentiment_confidence=abs(signal.sentiment_score or 0) * 100,
        technical_summary=_format_technical_summary(signal),
        volume_summary="Spike" if signal.volume_spike else "Normal",
        sector_performance=signal.sector_momentum or "Unknown",
        market_trend=get_index_trend("NIFTY"),
        current_price=price,
    )


def analyze_signal_with_llm(
    signal: Signal,
    session: Optional[Session] = None,
    client: Optional[OllamaClient] = None,
) -> Optional[Recommendation]:
    client = client or OllamaClient()

    def _run(sess: Session) -> Optional[Recommendation]:
        if not client.is_available():
            logger.warning("Ollama not available; skipping LLM for %s", signal.symbol)
            return None

        prompt = build_prompt(signal.symbol, signal, sess)
        raw = client.generate(
            prompt,
            system=f"You are a conservative Indian market analyst. {DISCLAIMER}",
        )
        if not raw:
            return None

        parsed = parse_llm_response(raw)
        rec = Recommendation(
            signal_id=signal.id,
            symbol=signal.symbol,
            recommendation=parsed.recommendation,
            confidence=parsed.confidence,
            risk_level=parsed.risk_level,
            entry_price=parsed.entry_price or signal.current_price,
            stop_loss=parsed.stop_loss,
            target_price=parsed.target_price,
            holding_period=parsed.holding_period,
            reasoning=parsed.reasoning,
            llm_raw_response=raw,
            approved=False,
        )
        sess.add(rec)
        sess.flush()
        return rec

    if session is not None:
        return _run(session)

    with get_db_session() as sess:
        signal_ref = sess.merge(signal)
        return _run(sess)


def analyze_top_signals(limit: Optional[int] = None) -> list[Recommendation]:
    settings = get_settings()
    limit = limit or settings.top_signals_for_llm
    client = OllamaClient()
    recommendations: list[Recommendation] = []

    with get_db_session() as session:
        signals = (
            session.query(Signal)
            .filter(Signal.signal_type.in_(["BUY", "WATCHLIST"]))
            .order_by(Signal.confidence.desc())
            .limit(limit)
            .all()
        )
        for signal in signals:
            rec = analyze_signal_with_llm(signal, session=session, client=client)
            if rec:
                recommendations.append(rec)

    return recommendations
