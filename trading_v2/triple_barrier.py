from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import pandas as pd

@dataclass
class BarrierSpec:
    pt_pct: float = 0.08
    sl_pct: float = 0.04
    max_hold_days: int = 60


def label_entry(df: pd.DataFrame, entry_idx: int, spec: BarrierSpec) -> int:
    """Return +1/-1/0 depending on which barrier is touched first after entry_idx.

    Uses Close only (EOD), consistent with the rest of the dashboard.
    """
    if df is None or df.empty:
        return 0
    if entry_idx < 0 or entry_idx >= len(df):
        return 0

    entry_price = float(df['Close'].iloc[entry_idx])
    pt = entry_price * (1.0 + spec.pt_pct)
    sl = entry_price * (1.0 - spec.sl_pct)

    entry_date = df.index[entry_idx]
    # forward window: next bars until vertical barrier
    end_date = entry_date + pd.Timedelta(days=int(spec.max_hold_days))
    fwd = df.loc[(df.index > entry_date) & (df.index <= end_date)]
    if fwd.empty:
        return 0

    # first barrier touched (Close-based)
    for _, row in fwd.iterrows():
        c = float(row['Close'])
        if c >= pt:
            return +1
        if c <= sl:
            return -1
    return 0


def label_entries(df: pd.DataFrame, entry_indices: List[int], spec: BarrierSpec) -> List[int]:
    return [label_entry(df, i, spec) for i in entry_indices]
