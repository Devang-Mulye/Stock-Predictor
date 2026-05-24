"""Smoke tests for core modules."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import get_settings
from data.db import init_db, get_db_session, NewsArticle
from news_engine.pipeline import clean_text, detect_keywords, title_hash
from news_engine.ticker_mapper import map_text_to_tickers
from risk_engine.manager import RiskManager
from data.db import Recommendation


def test_settings_defaults():
    settings = get_settings()
    assert settings.total_capital == 30_000
    assert settings.max_daily_loss == 1_000


def test_pipeline_helpers():
    text = "ONGC receives major contract and profit rise expected"
    cleaned = clean_text(text)
    assert "ONGC" in cleaned
    bullish, bearish = detect_keywords(cleaned)
    assert "contract" in bullish
    assert title_hash("Hello World") == title_hash("hello   world")


def test_ticker_mapping():
    matches = map_text_to_tickers("Reliance Industries reports strong earnings")
    tickers = [m.ticker for m in matches]
    assert "RELIANCE" in tickers


def test_db_init():
    init_db()
    with get_db_session() as session:
        count = session.query(NewsArticle).count()
        assert count >= 0


def test_risk_manager_defensive():
    init_db()
    manager = RiskManager()
    with get_db_session() as session:
        assert isinstance(manager.is_defensive_mode(session), bool)


def test_risk_rejects_poor_rr():
    init_db()
    manager = RiskManager()
    rec = Recommendation(
        symbol="BEL",
        recommendation="BUY",
        confidence=80,
        entry_price=100,
        stop_loss=95,
        target_price=102,
    )
    with get_db_session() as session:
        assessment = manager.assess_recommendation(rec, session)
        assert assessment.risk_reward_ratio < 2.0
        assert any("R:R" in r for r in assessment.rejection_reasons)
