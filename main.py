"""Full pipeline orchestration (Step 21)."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apscheduler.schedulers.blocking import BlockingScheduler

from alerts.notifier import create_alert_for_recommendation
from config.settings import get_settings
from data.db import NewsArticle, PipelineRun, Recommendation, get_db_session, init_db
from llm_engine.analyzer import analyze_top_signals
from news_engine.pipeline import process_articles
from news_engine.scraper import scrape_all_sources
from news_engine.ticker_mapper import map_article_tickers
from portfolio_engine.manager import PortfolioManager
from risk_engine.manager import apply_risk_to_recommendation
from sentiment_engine.analyzer import analyze_and_persist
from technical_engine.signals import generate_signals_for_symbols, get_tickers_from_recent_news

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("pipeline")


def _setup_file_logging():
    log_dir = get_settings().logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(fh)


def run_pipeline() -> dict:
    """Execute the full analysis pipeline once."""
    init_db()
    settings = get_settings()
    stats = {
        "articles_fetched": 0,
        "articles_saved": 0,
        "sentiment_analyzed": 0,
        "signals_generated": 0,
        "recommendations_created": 0,
        "alerts_created": 0,
    }

    with get_db_session() as session:
        run = PipelineRun(status="running", started_at=datetime.utcnow())
        session.add(run)
        session.flush()

        try:
            logger.info("Step 1-2: Scraping and processing news")
            raw = scrape_all_sources()
            stats["articles_fetched"] = len(raw)
            saved = process_articles(raw, session=session)
            stats["articles_saved"] = len(saved)

            logger.info("Step 3: Sentiment analysis")
            stats["sentiment_analyzed"] = analyze_and_persist(session=session)

            logger.info("Step 4: Ticker mapping")
            articles = saved if saved else []
            if not articles:
                articles = (
                    session.query(NewsArticle)
                    .filter(NewsArticle.sentiment_label.isnot(None))
                    .order_by(NewsArticle.created_at.desc())
                    .limit(20)
                    .all()
                )
            for article in articles:
                map_article_tickers(article, session=session)

            logger.info("Step 5-7: Market data, indicators, signals")
            tickers = get_tickers_from_recent_news(session)
            signals = generate_signals_for_symbols(tickers, session=session)
            stats["signals_generated"] = len(signals)

            logger.info("Step 8: LLM reasoning")
            recommendations = analyze_top_signals(settings.top_signals_for_llm)
            stats["recommendations_created"] = len(recommendations)

            logger.info("Step 9-10: Risk and portfolio checks")
            pm = PortfolioManager()
            for rec in recommendations:
                rec_merged = session.merge(rec)
                apply_risk_to_recommendation(rec_merged, session=session)
                sector_warnings = pm.check_new_trade_sector(
                    rec_merged.symbol,
                    rec_merged.position_size_inr or 0,
                    session,
                )
                if sector_warnings:
                    rec_merged.reasoning = (rec_merged.reasoning or "") + "\n" + "; ".join(
                        sector_warnings
                    )

            logger.info("Step 12: Dashboard alerts")
            recent_recs = (
                session.query(Recommendation)
                .order_by(Recommendation.created_at.desc())
                .limit(settings.top_signals_for_llm)
                .all()
            )
            for rec in recent_recs:
                alert = create_alert_for_recommendation(rec, session=session)
                if alert:
                    stats["alerts_created"] += 1

            run.status = "completed"
            run.articles_fetched = stats["articles_fetched"]
            run.signals_generated = stats["signals_generated"]
            run.recommendations_created = stats["recommendations_created"]
            run.finished_at = datetime.utcnow()
            logger.info("Pipeline complete: %s", stats)

        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.utcnow()
            logger.exception("Pipeline failed")
            raise

    return stats


def start_scheduler():
    settings = get_settings()
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        "interval",
        minutes=settings.scrape_interval_minutes,
        id="stock_pipeline",
    )
    logger.info(
        "Scheduler started — running every %d minutes",
        settings.scrape_interval_minutes,
    )
    run_pipeline()
    scheduler.start()


def main():
    parser = argparse.ArgumentParser(description="Stock Predictor Pipeline")
    parser.add_argument("--once", action="store_true", help="Run pipeline once and exit")
    parser.add_argument("--schedule", action="store_true", help="Run on interval schedule")
    args = parser.parse_args()

    _setup_file_logging()

    if args.schedule:
        start_scheduler()
    else:
        stats = run_pipeline()
        print(stats)


if __name__ == "__main__":
    main()
