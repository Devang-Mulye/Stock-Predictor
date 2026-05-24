"""Backtesting engine with backtrader (Step 11)."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import backtrader as bt
import pandas as pd

from config.settings import get_settings
from data.db import BacktestRun, get_db_session
from technical_engine.market_data import fetch_ohlcv

logger = logging.getLogger(__name__)


@dataclass
class BacktestMetrics:
    win_rate: float
    avg_return: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    total_trades: int


class SwingStrategy(bt.Strategy):
    params = (
        ("rsi_min", 55),
        ("rsi_max", 75),
        ("stop_pct", 0.03),
        ("target_pct", 0.06),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.macd = bt.indicators.MACD(self.data.close)
        self.sma_vol = bt.indicators.SMA(self.data.volume, period=20)
        self.order = None

    def next(self):
        if self.order:
            return

        if not self.position:
            vol_spike = self.data.volume[0] > self.sma_vol[0] * 1.5
            macd_bull = self.macd.macd[0] > self.macd.signal[0]
            rsi_ok = self.params.rsi_min <= self.rsi[0] <= self.params.rsi_max
            if vol_spike and macd_bull and rsi_ok:
                size = int(self.broker.getcash() * 0.1 / self.data.close[0])
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            entry = self.position.price
            stop = entry * (1 - self.params.stop_pct)
            target = entry * (1 + self.params.target_pct)
            if self.data.close[0] <= stop or self.data.close[0] >= target:
                self.order = self.close()


def _compute_metrics(strat: bt.Strategy) -> BacktestMetrics:
    trades = strat.analyzers.trades.get_analysis()
    total = trades.get("total", {}).get("closed", 0)
    won = trades.get("won", {}).get("total", 0)
    win_rate = (won / total * 100) if total else 0.0

    returns = strat.analyzers.returns.get_analysis()
    avg_return = returns.get("ravg", 0.0) or 0.0

    dd = strat.analyzers.drawdown.get_analysis()
    max_dd = dd.get("max", {}).get("drawdown", 0.0) or 0.0

    sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio", 0.0) or 0.0

    pf = strat.analyzers.trades.get_analysis()
    gross_profit = pf.get("won", {}).get("pnl", {}).get("total", 0) or 0
    gross_loss = abs(pf.get("lost", {}).get("pnl", {}).get("total", 0) or 1)
    profit_factor = gross_profit / gross_loss if gross_loss else 0.0

    return BacktestMetrics(
        win_rate=round(win_rate, 2),
        avg_return=round(float(avg_return) * 100, 2),
        max_drawdown=round(float(max_dd), 2),
        sharpe_ratio=round(float(sharpe or 0), 2),
        profit_factor=round(profit_factor, 2),
        total_trades=total,
    )


def run_backtest(symbol: str, days: int = 365, persist: bool = True) -> BacktestMetrics:
    settings = get_settings()
    df = fetch_ohlcv(symbol, "1d")
    if df is None or df.empty:
        raise ValueError(f"No data for {symbol}")

    cutoff = datetime.utcnow() - timedelta(days=days)
    df = df[df.index >= pd.Timestamp(cutoff)]
    if len(df) < 50:
        raise ValueError(f"Insufficient history for {symbol}")

    cerebro = bt.Cerebro()
    data = bt.feeds.PandasData(
        dataname=df.rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
    )
    cerebro.adddata(data)
    cerebro.addstrategy(
        SwingStrategy,
        rsi_min=settings.rsi_buy_min,
        rsi_max=settings.rsi_buy_max,
    )
    cerebro.broker.setcash(settings.total_capital)
    cerebro.broker.setcommission(commission=0.001)

    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")

    results = cerebro.run()
    strat = results[0]
    metrics = _compute_metrics(strat)

    if persist:
        with get_db_session() as session:
            session.add(
                BacktestRun(
                    symbol=symbol,
                    days=days,
                    win_rate=metrics.win_rate,
                    avg_return=metrics.avg_return,
                    max_drawdown=metrics.max_drawdown,
                    sharpe_ratio=metrics.sharpe_ratio,
                    profit_factor=metrics.profit_factor,
                    total_trades=metrics.total_trades,
                    metrics_json=json.dumps(metrics.__dict__),
                )
            )

    logger.info("Backtest %s: %s", symbol, metrics)
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Run backtest for a symbol")
    parser.add_argument("--symbol", default="BEL")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()
    metrics = run_backtest(args.symbol, args.days, persist=not args.no_persist)
    print(json.dumps(metrics.__dict__, indent=2))


if __name__ == "__main__":
    main()
