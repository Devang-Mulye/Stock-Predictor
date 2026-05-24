"""Price action pattern detection (Step 6)."""

from __future__ import annotations

from typing import Any

import pandas as pd


def detect_price_action(df: pd.DataFrame) -> dict[str, Any]:
    if len(df) < 5:
        return {}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    recent = df.tail(20)

    high_20 = float(recent["high"].max())
    low_20 = float(recent["low"].min())
    close = float(last["close"])

    breakout_up = close >= high_20 * 0.998 and float(prev["close"]) < high_20
    breakout_down = close <= low_20 * 1.002 and float(prev["close"]) > low_20

    range_pct = (high_20 - low_20) / low_20 if low_20 else 0
    consolidation = range_pct < 0.05

    gap_up = float(last["open"]) > float(prev["close"]) * 1.01
    gap_down = float(last["open"]) < float(prev["close"]) * 0.99

    body = abs(float(last["close"]) - float(last["open"]))
    upper_shadow = float(last["high"]) - max(float(last["close"]), float(last["open"]))
    lower_shadow = min(float(last["close"]), float(last["open"])) - float(last["low"])

    doji = body < (float(last["high"]) - float(last["low"])) * 0.1
    hammer = lower_shadow > body * 2 and upper_shadow < body
    shooting_star = upper_shadow > body * 2 and lower_shadow < body

    return {
        "support": low_20,
        "resistance": high_20,
        "breakout_up": breakout_up,
        "breakout_down": breakout_down,
        "consolidation": consolidation,
        "gap_up": gap_up,
        "gap_down": gap_down,
        "candle_doji": doji,
        "candle_hammer": hammer,
        "candle_shooting_star": shooting_star,
    }
