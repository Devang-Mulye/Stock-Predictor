"""Streamlit dashboard (Steps 13 & 24)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.prompts import DISCLAIMER
from config.settings import get_settings
from data.db import (
    Alert,
    NewsArticle,
    Recommendation,
    Signal,
    init_db,
)
from data.db import get_db_session
from portfolio_engine.manager import PortfolioManager
from technical_engine.market_data import fetch_ohlcv, get_index_trend, get_latest_price

st.set_page_config(
    page_title="Stock Predictor — Indian Market AI Advisor",
    page_icon="📈",
    layout="wide",
)

init_db()
settings = get_settings()


def disclaimer_banner():
    st.warning(DISCLAIMER)


@st.cache_data(ttl=300)
def load_index_snapshot():
    nifty = get_latest_price("NIFTY")
    bank = get_latest_price("BANKNIFTY")
    return {
        "NIFTY": nifty,
        "NIFTY_trend": get_index_trend("NIFTY"),
        "BANKNIFTY": bank,
        "BANKNIFTY_trend": get_index_trend("BANKNIFTY"),
    }


def tab_market_overview():
    st.subheader("Market Overview")
    snap = load_index_snapshot()
    c1, c2 = st.columns(2)
    with c1:
        st.metric("NIFTY", f"₹{snap['NIFTY']:,.2f}" if snap["NIFTY"] else "N/A", snap["NIFTY_trend"])
    with c2:
        st.metric(
            "BANKNIFTY",
            f"₹{snap['BANKNIFTY']:,.2f}" if snap["BANKNIFTY"] else "N/A",
            snap["BANKNIFTY_trend"],
        )

    st.subheader("Sector Watchlist")
    sectors = {}
    with open(settings.project_root / "data" / "ticker_aliases.json", encoding="utf-8") as f:
        aliases = json.load(f)
    for ticker, info in aliases.items():
        sector = info.get("sector", "Other")
        sectors.setdefault(sector, []).append(ticker)

    sector_rows = []
    for sector, tickers in sectors.items():
        prices = []
        for t in tickers[:2]:
            p = get_latest_price(t)
            if p:
                prices.append(p)
        sector_rows.append({"Sector": sector, "Stocks": len(tickers), "Sample": ", ".join(tickers[:3])})
    st.dataframe(pd.DataFrame(sector_rows), use_container_width=True)


def tab_watchlist():
    st.subheader("Watchlist & AI Opportunities")
    with get_db_session() as session:
        recs = (
            session.query(Recommendation)
            .order_by(Recommendation.confidence.desc())
            .limit(20)
            .all()
        )
        if recs:
            rows = [
                {
                    "Symbol": r.symbol,
                    "Action": r.recommendation,
                    "Confidence": f"{r.confidence:.0f}%",
                    "Entry": r.entry_price,
                    "Target": r.target_price,
                    "Approved": r.approved,
                }
                for r in recs
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("Run the pipeline to generate recommendations.")

    st.subheader("Default Watchlist")
    prices = []
    for sym in settings.default_watchlist:
        p = get_latest_price(sym)
        prices.append({"Symbol": sym, "Price": f"₹{p:.2f}" if p else "N/A"})
    st.dataframe(pd.DataFrame(prices), use_container_width=True)


def tab_signals():
    st.subheader("Active Signals")
    with get_db_session() as session:
        signals = (
            session.query(Signal)
            .order_by(Signal.created_at.desc())
            .limit(30)
            .all()
        )
    if not signals:
        st.info("No signals yet.")
        return
    rows = []
    for s in signals:
        reasons = json.loads(s.reasons) if s.reasons else []
        rows.append(
            {
                "Symbol": s.symbol,
                "Signal": s.signal_type,
                "Confidence": f"{s.confidence:.0f}%",
                "RSI": f"{s.rsi:.1f}" if s.rsi else "-",
                "Price": f"₹{s.current_price:.2f}" if s.current_price else "-",
                "Reasons": "; ".join(reasons[:2]),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def tab_portfolio():
    st.subheader("Portfolio Tracking")
    pm = PortfolioManager()
    summary = pm.summarize()
    c1, c2, c3 = st.columns(3)
    c1.metric("Portfolio Value", f"₹{summary.total_value:,.0f}")
    c2.metric("Unrealized P&L", f"₹{summary.unrealized_pnl:,.0f}")
    c3.metric("Cost Basis", f"₹{summary.total_cost:,.0f}")

    if summary.sector_weights:
        st.bar_chart(pd.Series(summary.sector_weights))

    for w in summary.concentration_warnings:
        st.error(w)
    for h in summary.diversification_hints:
        st.info(h)

    with st.expander("Add Position (manual)"):
        sym = st.text_input("Symbol", "BEL")
        qty = st.number_input("Quantity", min_value=1.0, value=10.0)
        entry = st.number_input("Entry Price", min_value=0.0, value=300.0)
        if st.button("Add"):
            pm.add_position(sym.upper(), qty, entry)
            st.success(f"Added {sym}")
            st.rerun()


def tab_news():
    st.subheader("News Feed")
    with get_db_session() as session:
        articles = (
            session.query(NewsArticle)
            .filter(NewsArticle.is_spam == False)  # noqa: E712
            .order_by(NewsArticle.created_at.desc())
            .limit(25)
            .all()
        )
    for a in articles:
        sent = a.sentiment_label or "Pending"
        conf = f"{a.sentiment_confidence:.0f}%" if a.sentiment_confidence else ""
        with st.expander(f"{a.title[:80]} — {a.source}"):
            st.caption(f"Sentiment: {sent} {conf}")
            st.write(a.summary or a.cleaned_text or "")
            if a.bullish_keywords:
                st.success(f"Bullish: {a.bullish_keywords}")
            if a.bearish_keywords:
                st.error(f"Bearish: {a.bearish_keywords}")
            st.link_button("Open article", a.url)


def tab_alerts():
    st.subheader("Alerts Inbox")
    from alerts.notifier import AlertNotifier

    notifier = AlertNotifier()
    unread = notifier.get_unread_count()
    st.metric("Unread Alerts", unread)

    alerts = notifier.list_alerts(limit=30)
    for alert in alerts:
        badge = "🔴" if not alert.is_read else "✅"
        with st.expander(f"{badge} {alert.title}"):
            st.text(alert.message)
            if not alert.is_read and st.button("Mark read", key=f"read_{alert.id}"):
                notifier.mark_read(alert.id)
                st.rerun()


def main():
    st.title("Local AI Stock Advisor")
    st.caption("Indian market research assistant — advisory only")
    disclaimer_banner()

    tabs = st.tabs(
        [
            "Market",
            "Watchlist",
            "Signals",
            "Portfolio",
            "News",
            "Alerts",
        ]
    )
    with tabs[0]:
        tab_market_overview()
    with tabs[1]:
        tab_watchlist()
    with tabs[2]:
        tab_signals()
    with tabs[3]:
        tab_portfolio()
    with tabs[4]:
        tab_news()
    with tabs[5]:
        tab_alerts()


if __name__ == "__main__":
    main()
