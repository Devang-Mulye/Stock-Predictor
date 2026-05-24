"""Alerting system — dashboard-only v1 (Step 12)."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from config.prompts import DISCLAIMER
from data.db import Alert, Recommendation, get_db_session

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Stub for future Telegram integration."""

    def send(self, message: str) -> bool:
        logger.debug("Telegram stub: %s", message[:80])
        return False


class DiscordNotifier:
    """Stub for future Discord integration."""

    def send(self, message: str) -> bool:
        logger.debug("Discord stub: %s", message[:80])
        return False


class AlertNotifier:
    def __init__(self):
        self.telegram = TelegramNotifier()
        self.discord = DiscordNotifier()

    def create_alert(
        self,
        symbol: str,
        alert_type: str,
        title: str,
        message: str,
        recommendation_id: Optional[int] = None,
        session: Optional[Session] = None,
    ) -> Alert:
        full_message = f"{message}\n\n{DISCLAIMER}"

        def _create(sess: Session) -> Alert:
            alert = Alert(
                symbol=symbol,
                alert_type=alert_type,
                title=title,
                message=full_message,
                recommendation_id=recommendation_id,
                is_read=False,
            )
            sess.add(alert)
            sess.flush()
            return alert

        if session is not None:
            return _create(session)

        with get_db_session() as sess:
            return _create(sess)

    def get_unread_count(self, session: Optional[Session] = None) -> int:
        def _count(sess: Session) -> int:
            return sess.query(Alert).filter(Alert.is_read == False).count()  # noqa: E712

        if session is not None:
            return _count(session)

        with get_db_session() as sess:
            return _count(sess)

    def mark_read(self, alert_id: int, session: Optional[Session] = None) -> None:
        def _mark(sess: Session) -> None:
            alert = sess.query(Alert).filter(Alert.id == alert_id).first()
            if alert:
                alert.is_read = True

        if session is not None:
            _mark(session)
            return

        with get_db_session() as sess:
            _mark(sess)

    def list_alerts(self, limit: int = 50, unread_only: bool = False) -> list[Alert]:
        with get_db_session() as session:
            q = session.query(Alert).order_by(Alert.created_at.desc())
            if unread_only:
                q = q.filter(Alert.is_read == False)  # noqa: E712
            return q.limit(limit).all()


def create_alert_for_recommendation(
    rec: Recommendation,
    session: Optional[Session] = None,
) -> Optional[Alert]:
    if not rec.approved:
        return None

    notifier = AlertNotifier()
    def _fmt_price(val: Optional[float]) -> str:
        return f"₹{val:.2f}" if val is not None else "N/A"

    title = f"{rec.recommendation} SIGNAL — {rec.symbol}"
    conf = f"{rec.confidence:.0f}%" if rec.confidence is not None else "N/A"
    pos = f"₹{rec.position_size_inr:.0f}" if rec.position_size_inr else "N/A"
    message = (
        f"Stock: {rec.symbol}\n"
        f"Entry: {_fmt_price(rec.entry_price)}\n"
        f"Stop Loss: {_fmt_price(rec.stop_loss)}\n"
        f"Target: {_fmt_price(rec.target_price)}\n"
        f"Confidence: {conf}\n"
        f"Risk: {rec.risk_level or 'N/A'}\n"
        f"Position size: {pos}\n"
        f"Reason:\n{rec.reasoning or 'N/A'}"
    )
    return notifier.create_alert(
        symbol=rec.symbol,
        alert_type=rec.recommendation,
        title=title,
        message=message,
        recommendation_id=rec.id,
        session=session,
    )
