"""Technical analysis indicators (Step 6)."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

# Original `pandas-ta` is unavailable on PyPI; `pandas-ta-classic` provides df.ta
_HAS_PANDAS_TA = False
try:
    import pandas_ta  # noqa: F401

    _HAS_PANDAS_TA = True
except ImportError:
    try:
        import pandas_ta_classic  # noqa: F401

        _HAS_PANDAS_TA = True
    except ImportError:
        pass

from technical_engine.patterns import detect_price_action


def _ensure_ta():
    if not _HAS_PANDAS_TA:
        raise ImportError(
            "Install technical analysis support: pip install pandas-ta-classic"
        )


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    _ensure_ta()
    out = df.copy()
    out.ta.ema(length=20, append=True)
    out.ta.ema(length=50, append=True)
    out.ta.ema(length=200, append=True)
    out.ta.sma(length=20, append=True)
    out.ta.rsi(length=14, append=True)
    out.ta.macd(append=True)
    out.ta.stochrsi(append=True)
    out.ta.atr(length=14, append=True)
    out.ta.bbands(length=20, append=True)
    out.ta.obv(append=True)
    out.ta.vwap(append=True)
    return out


def _col(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def compute_indicators(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or len(df) < 30:
        return {}

    enriched = add_indicators(df)
    last = enriched.iloc[-1]
    prev = enriched.iloc[-2] if len(enriched) > 1 else last

    ema20 = _col(enriched, "EMA_20")
    ema50 = _col(enriched, "EMA_50")
    ema200 = _col(enriched, "EMA_200")
    rsi_col = _col(enriched, "RSI_14")
    macd_col = _col(enriched, "MACD_12_26_9")
    macd_sig = _col(enriched, "MACDs_12_26_9")
    atr_col = _col(enriched, "ATRr_14", "ATR_14")
    bb_lower = _col(enriched, "BBL_20_2.0")
    bb_upper = _col(enriched, "BBU_20_2.0")
    obv_col = _col(enriched, "OBV")
    vwap_col = _col(enriched, "VWAP_D")

    close = float(last["close"])
    volume = float(last.get("volume", 0) or 0)
    avg_vol = float(enriched["volume"].tail(20).mean()) if "volume" in enriched.columns else 0

    rsi = float(last[rsi_col]) if rsi_col else None
    macd_val = float(last[macd_col]) if macd_col else None
    macd_signal_val = float(last[macd_sig]) if macd_sig else None
    prev_macd = float(prev[macd_col]) if macd_col else None
    prev_macd_sig = float(prev[macd_sig]) if macd_sig else None

    macd_cross = "none"
    if macd_val is not None and macd_signal_val is not None:
        if prev_macd is not None and prev_macd_sig is not None:
            if prev_macd <= prev_macd_sig and macd_val > macd_signal_val:
                macd_cross = "bullish"
            elif prev_macd >= prev_macd_sig and macd_val < macd_signal_val:
                macd_cross = "bearish"

    volume_spike = avg_vol > 0 and volume >= avg_vol * 1.5

    snapshot = {
        "close": close,
        "ema20": float(last[ema20]) if ema20 else None,
        "ema50": float(last[ema50]) if ema50 else None,
        "ema200": float(last[ema200]) if ema200 else None,
        "rsi": rsi,
        "macd": macd_val,
        "macd_signal": macd_signal_val,
        "macd_cross": macd_cross,
        "atr": float(last[atr_col]) if atr_col else None,
        "bb_lower": float(last[bb_lower]) if bb_lower else None,
        "bb_upper": float(last[bb_upper]) if bb_upper else None,
        "obv": float(last[obv_col]) if obv_col else None,
        "vwap": float(last[vwap_col]) if vwap_col else None,
        "volume": volume,
        "avg_volume_20": avg_vol,
        "volume_spike": volume_spike,
    }
    snapshot.update(detect_price_action(enriched))
    return snapshot
