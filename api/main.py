"""FastAPI HTTP layer for pipeline status and data access."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.prompts import DISCLAIMER
from config.settings import get_settings
from data.db import Alert, PipelineRun, Recommendation, Signal, get_db_session, init_db
from main import run_pipeline

app = FastAPI(title="Stock Predictor API", version="1.0.0")


class HealthResponse(BaseModel):
    status: str
    disclaimer: str


class PipelineStats(BaseModel):
    articles_fetched: int
    articles_saved: int
    sentiment_analyzed: int
    signals_generated: int
    recommendations_created: int
    alerts_created: int


@app.on_event("startup")
def startup():
    init_db()
    get_settings().logs_dir.mkdir(parents=True, exist_ok=True)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", disclaimer=DISCLAIMER)


@app.post("/pipeline/run", response_model=PipelineStats)
def trigger_pipeline():
    stats = run_pipeline()
    return PipelineStats(**stats)


@app.get("/signals")
def list_signals(limit: int = 20):
    with get_db_session() as session:
        rows = (
            session.query(Signal)
            .order_by(Signal.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "symbol": s.symbol,
                "signal_type": s.signal_type,
                "confidence": s.confidence,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in rows
        ]


@app.get("/recommendations")
def list_recommendations(limit: int = 20):
    with get_db_session() as session:
        rows = (
            session.query(Recommendation)
            .order_by(Recommendation.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "symbol": r.symbol,
                "recommendation": r.recommendation,
                "confidence": r.confidence,
                "approved": r.approved,
                "entry_price": r.entry_price,
                "stop_loss": r.stop_loss,
                "target_price": r.target_price,
            }
            for r in rows
        ]


@app.get("/alerts/unread/count")
def unread_alerts():
    with get_db_session() as session:
        count = session.query(Alert).filter(Alert.is_read == False).count()  # noqa: E712
        return {"unread": count}


@app.get("/pipeline/runs")
def pipeline_runs(limit: int = 10):
    with get_db_session() as session:
        runs = (
            session.query(PipelineRun)
            .order_by(PipelineRun.started_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "status": r.status,
                "articles_fetched": r.articles_fetched,
                "signals_generated": r.signals_generated,
                "recommendations_created": r.recommendations_created,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ]
