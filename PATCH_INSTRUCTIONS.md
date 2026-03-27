from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List
import pandas as pd

REQUIRED_COLS = [
    'Close','BB_Upper','BB_Lower','BB_Middle','RSI','MACD','MACD_Signal','MACD_Hist','ADX','+DI','-DI'
]

@dataclass
class FeatureRow:
    date: str
    close: float
    rsi: float
    bb_pos: float
    macd: float
    macd_signal: float
    macd_hist: float
    macd_cross_up: bool
    hist_rising: bool
    adx: float
    pdi: float
    mdi: float


def ensure_columns(df: pd.DataFrame) -> List[str]:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    return missing


def build_features(df: pd.DataFrame, adx_thr: float) -> Dict[str, Any]:
    """Compute derived features for the last row and also provide a small feature dict for logging."""
    if df is None or df.empty:
        raise ValueError('Empty data')

    missing = ensure_columns(df)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last

    denom = float(last['BB_Upper'] - last['BB_Lower'])
    bb_pos = float((last['Close'] - last['BB_Lower']) / denom) if denom != 0 else 0.5

    macd_cross_up = bool((last['MACD'] > last['MACD_Signal']) and (prev['MACD'] <= prev['MACD_Signal']))
    hist_rising = bool(last['MACD_Hist'] > prev['MACD_Hist']) if len(df) >= 2 else False
    downtrend_strength = bool((last['ADX'] > adx_thr) and (last['-DI'] > last['+DI']))

    return {
        'rsi': float(last['RSI']),
        'close': float(last['Close']),
        'bb_pos': bb_pos,
        'macd_hist': float(last['MACD_Hist']),
        'macd_cross_up': macd_cross_up,
        'hist_rising': hist_rising,
        'adx': float(last['ADX']),
        'pdi': float(last['+DI']),
        'mdi': float(last['-DI']),
        'downtrend_strength': downtrend_strength,
        'bb_middle': float(last['BB_Middle']),
        'bb_lower': float(last['BB_Lower']),
        'macd': float(last['MACD']),
        'macd_signal': float(last['MACD_Signal']),
    }
