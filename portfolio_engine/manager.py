"""Portfolio management engine (Step 10)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from config.settings import get_settings
from data.db import Position, get_db_session
from technical_engine.market_data import get_latest_price


@dataclass
class PositionSummary:
    symbol: str
    sector: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    allocation_pct: float


@dataclass
class PortfolioSummary:
    total_value: float
    total_cost: float
    unrealized_pnl: float
    sector_weights: dict[str, float]
    concentration_warnings: list[str]
    diversification_hints: list[str]


class PortfolioManager:
    def __init__(self):
        self.settings = get_settings()
        self._aliases = self._load_aliases()

    def _load_aliases(self) -> dict:
        path = self.settings.project_root / "data" / "ticker_aliases.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _sector(self, symbol: str) -> str:
        return self._aliases.get(symbol, {}).get("sector", "Unknown")

    def add_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        stop_loss: Optional[float] = None,
        target_price: Optional[float] = None,
        notes: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Position:
        position = Position(
            symbol=symbol.upper(),
            sector=self._sector(symbol),
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            notes=notes,
            is_open=True,
        )

        def _add(sess: Session) -> Position:
            sess.add(position)
            sess.flush()
            return position

        if session is not None:
            return _add(session)

        with get_db_session() as sess:
            return _add(sess)

    def close_position(
        self,
        position_id: int,
        session: Optional[Session] = None,
    ) -> Optional[Position]:
        def _close(sess: Session) -> Optional[Position]:
            pos = sess.query(Position).filter(Position.id == position_id).first()
            if pos:
                pos.is_open = False
                pos.closed_at = datetime.utcnow()
            return pos

        if session is not None:
            return _close(session)

        with get_db_session() as sess:
            return _close(sess)

    def get_open_positions(self, session: Optional[Session] = None) -> list[Position]:
        def _get(sess: Session) -> list[Position]:
            return sess.query(Position).filter(Position.is_open == True).all()  # noqa: E712

        if session is not None:
            return _get(session)

        with get_db_session() as sess:
            return _get(sess)

    def summarize(self, session: Optional[Session] = None) -> PortfolioSummary:
        def _summarize(sess: Session) -> PortfolioSummary:
            positions = self.get_open_positions(sess)
            summaries: list[PositionSummary] = []
            total_value = 0.0
            total_cost = 0.0
            sector_values: dict[str, float] = {}

            for pos in positions:
                current = get_latest_price(pos.symbol) or pos.entry_price
                cost = pos.entry_price * pos.quantity
                value = current * pos.quantity
                pnl = value - cost
                total_cost += cost
                total_value += value
                sector = pos.sector or self._sector(pos.symbol)
                sector_values[sector] = sector_values.get(sector, 0) + value
                summaries.append(
                    PositionSummary(
                        symbol=pos.symbol,
                        sector=sector,
                        quantity=pos.quantity,
                        entry_price=pos.entry_price,
                        current_price=current,
                        unrealized_pnl=pnl,
                        unrealized_pnl_pct=(pnl / cost * 100) if cost else 0,
                        allocation_pct=0,
                    )
                )

            if total_value > 0:
                for s in summaries:
                    s.allocation_pct = (s.current_price * s.quantity / total_value) * 100

            sector_weights = {
                k: (v / total_value * 100) if total_value else 0
                for k, v in sector_values.items()
            }

            warnings = []
            hints = []
            for sector, weight in sector_weights.items():
                if weight > self.settings.max_sector_concentration_pct * 100:
                    warnings.append(
                        f"Overexposure to {sector}: {weight:.1f}% of portfolio"
                    )
                    hints.append(f"Consider reducing {sector} exposure")

            ideal_sectors = ["Banking", "Defense", "Pharma", "Energy", "IT"]
            missing = [s for s in ideal_sectors if s not in sector_weights]
            if missing:
                hints.append(f"Consider diversifying into: {', '.join(missing[:3])}")

            return PortfolioSummary(
                total_value=total_value,
                total_cost=total_cost,
                unrealized_pnl=total_value - total_cost,
                sector_weights=sector_weights,
                concentration_warnings=warnings,
                diversification_hints=hints,
            )

        if session is not None:
            return _summarize(session)

        with get_db_session() as sess:
            return _summarize(sess)

    def check_new_trade_sector(
        self,
        symbol: str,
        trade_value: float,
        session: Session,
    ) -> list[str]:
        summary = self.summarize(session)
        sector = self._sector(symbol)
        if summary.total_value + trade_value == 0:
            return []
        new_sector_weight = (
            summary.sector_weights.get(sector, 0) * summary.total_value / 100
            + trade_value
        ) / (summary.total_value + trade_value) * 100
        if new_sector_weight > self.settings.max_sector_concentration_pct * 100:
            return [f"Adding {symbol} would increase {sector} to ~{new_sector_weight:.0f}%"]
        return []
