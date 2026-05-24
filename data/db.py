"""SQLite persistence layer (Step 14)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Generator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import get_settings


class Base(DeclarativeBase):
    pass


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(1024), unique=True, nullable=False, index=True)
    title = Column(String(512), nullable=False)
    source = Column(String(128), nullable=False)
    source_credibility = Column(Float, default=0.5)
    published_at = Column(DateTime, nullable=True)
    raw_text = Column(Text, nullable=True)
    cleaned_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    title_hash = Column(String(64), index=True)
    bullish_keywords = Column(Text, nullable=True)
    bearish_keywords = Column(Text, nullable=True)
    sentiment_label = Column(String(32), nullable=True)
    sentiment_score = Column(Float, nullable=True)
    sentiment_confidence = Column(Float, nullable=True)
    is_spam = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ArticleTicker(Base):
    __tablename__ = "article_tickers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, index=True, nullable=False)
    ticker = Column(String(32), index=True, nullable=False)
    company_name = Column(String(256), nullable=True)
    match_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OHLCV(Base):
    __tablename__ = "ohlcv"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), index=True, nullable=False)
    interval = Column(String(16), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=True)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), index=True, nullable=False)
    signal_type = Column(String(16), nullable=False)
    confidence = Column(Float, nullable=False)
    reasons = Column(Text, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    rsi = Column(Float, nullable=True)
    macd_signal = Column(String(32), nullable=True)
    volume_spike = Column(Boolean, default=False)
    sector_momentum = Column(String(64), nullable=True)
    current_price = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, nullable=True)
    symbol = Column(String(32), index=True, nullable=False)
    recommendation = Column(String(16), nullable=False)
    confidence = Column(Float, nullable=True)
    risk_level = Column(String(16), nullable=True)
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    holding_period = Column(String(64), nullable=True)
    position_size_inr = Column(Float, nullable=True)
    risk_reward_ratio = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    llm_raw_response = Column(Text, nullable=True)
    approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), index=True, nullable=False)
    sector = Column(String(64), nullable=True)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    is_open = Column(Boolean, default=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False)
    alert_type = Column(String(32), nullable=False)
    title = Column(String(256), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    recommendation_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False)
    days = Column(Integer, nullable=False)
    win_rate = Column(Float, nullable=True)
    avg_return = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)
    metrics_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(32), nullable=False)
    articles_fetched = Column(Integer, default=0)
    signals_generated = Column(Integer, default=0)
    recommendations_created = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        settings.models_cache_dir.mkdir(parents=True, exist_ok=True)
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        db_path = settings.project_root / "data"
        db_path.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False}
            if settings.database_url.startswith("sqlite")
            else {},
        )

        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            if settings.database_url.startswith("sqlite"):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False)
    return _SessionLocal


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
