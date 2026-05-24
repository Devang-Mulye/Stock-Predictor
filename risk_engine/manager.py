"""Risk management engine (Steps 9 & 19)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from config.settings import get_settings
from data.db import Position, Recommendation, get_db_session
from technical_engine.market_data import get_avg_volume, get_latest_price

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    approved: bool
    position_size_inr: float
    risk_reward_ratio: float
    defensive_mode: bool
    rejection_reasons: list[str]


class RiskManager:
    def __init__(self):
        self.settings = get_settings()

    def _realized_pnl(self, session: Session, since: datetime) -> float:
        closed = (
            session.query(Position)
            .filter(Position.is_open == False, Position.closed_at >= since)  # noqa: E712
            .all()
        )
        pnl = 0.0
        for pos in closed:
            if pos.closed_at and pos.entry_price:
                pnl += (pos.entry_price - pos.entry_price) * pos.quantity
        return pnl

    def _unrealized_daily_estimate(self, session: Session) -> float:
        open_positions = (
            session.query(Position).filter(Position.is_open == True).all()  # noqa: E712
        )
        loss = 0.0
        for pos in open_positions:
            price = get_latest_price(pos.symbol)
            if price and pos.entry_price:
                change = (price - pos.entry_price) * pos.quantity
                if change < 0:
                    loss += abs(change)
        return loss

    def is_defensive_mode(self, session: Session) -> bool:
        now = datetime.utcnow()
        daily_loss = self._unrealized_daily_estimate(session)
        weekly_since = now - timedelta(days=7)
        weekly_loss = daily_loss + abs(min(0, self._realized_pnl(session, weekly_since)))

        if daily_loss >= self.settings.max_daily_loss:
            logger.warning("Defensive mode: daily loss threshold")
            return True
        if weekly_loss >= self.settings.max_weekly_loss:
            logger.warning("Defensive mode: weekly loss threshold")
            return True
        return False

    def _check_liquidity(self, symbol: str, price: Optional[float]) -> list[str]:
        reasons = []
        price = price or get_latest_price(symbol)
        if price and price < self.settings.min_stock_price_inr:
            reasons.append(f"Price below minimum (₹{self.settings.min_stock_price_inr})")
        avg_vol = get_avg_volume(symbol)
        if avg_vol < self.settings.min_avg_volume:
            reasons.append(f"Low liquidity (avg vol {avg_vol:.0f})")
        return reasons

    def _check_fomo(self, symbol: str) -> list[str]:
        from technical_engine.market_data import load_ohlcv_from_db

        df = load_ohlcv_from_db(symbol, "1d")
        if df is None or len(df) < 2:
            return []
        prev_close = float(df["close"].iloc[-2])
        last_close = float(df["close"].iloc[-1])
        if prev_close > 0:
            spike = ((last_close - prev_close) / prev_close) * 100
            if spike > self.settings.max_day_spike_pct:
                return [f"FOMO filter: {spike:.1f}% single-day spike"]
        return []

    def assess_recommendation(
        self,
        rec: Recommendation,
        session: Session,
    ) -> RiskAssessment:
        reasons: list[str] = []
        defensive = self.is_defensive_mode(session)

        entry = rec.entry_price or get_latest_price(rec.symbol)
        stop = rec.stop_loss
        target = rec.target_price

        if not entry:
            reasons.append("Missing entry price")
            return RiskAssessment(False, 0, 0, defensive, reasons)

        liquidity_issues = self._check_liquidity(rec.symbol, entry)
        reasons.extend(liquidity_issues)
        reasons.extend(self._check_fomo(rec.symbol))

        if defensive and rec.recommendation == "BUY":
            reasons.append("Defensive mode active — BUY downgraded")
            rec.recommendation = "WATCH"

        risk_per_share = 0.0
        rr_ratio = 0.0
        if stop and entry:
            risk_per_share = abs(entry - stop)
            if target and risk_per_share > 0:
                reward = abs(target - entry)
                rr_ratio = reward / risk_per_share
                if rr_ratio < self.settings.min_risk_reward_ratio:
                    reasons.append(
                        f"R:R {rr_ratio:.2f} below minimum {self.settings.min_risk_reward_ratio}"
                    )

        max_risk_inr = self.settings.max_risk_per_trade_inr
        max_alloc = min(
            self.settings.max_allocation_inr,
            self.settings.max_trade_size_inr,
        )

        if risk_per_share > 0:
            shares_by_risk = max_risk_inr / risk_per_share
            position_size = min(shares_by_risk * entry, max_alloc)
        else:
            position_size = min(self.settings.min_trade_size_inr, max_alloc)

        position_size = max(
            min(position_size, self.settings.max_trade_size_inr),
            0,
        )

        approved = (
            len([r for r in reasons if "downgraded" not in r.lower()]) == 0
            or (defensive and rec.recommendation == "WATCH")
        )
        if liquidity_issues or any("R:R" in r for r in reasons):
            approved = False
        if defensive and rec.recommendation == "BUY":
            approved = False

        if not stop or not target:
            reasons.append("Missing stop loss or target from LLM")
            approved = False

        return RiskAssessment(
            approved=approved and rec.recommendation in ("BUY", "SELL", "WATCH"),
            position_size_inr=round(position_size, 2),
            risk_reward_ratio=round(rr_ratio, 2),
            defensive_mode=defensive,
            rejection_reasons=reasons,
        )


def apply_risk_to_recommendation(
    rec: Recommendation,
    session: Optional[Session] = None,
) -> RiskAssessment:
    manager = RiskManager()

    def _apply(sess: Session) -> RiskAssessment:
        assessment = manager.assess_recommendation(rec, sess)
        rec.position_size_inr = assessment.position_size_inr
        rec.risk_reward_ratio = assessment.risk_reward_ratio
        rec.approved = assessment.approved
        if assessment.rejection_reasons:
            rec.reasoning = (rec.reasoning or "") + "\nRisk: " + "; ".join(
                assessment.rejection_reasons
            )
        return assessment

    if session is not None:
        return _apply(session)

    with get_db_session() as sess:
        rec_ref = sess.merge(rec)
        return _apply(sess)
