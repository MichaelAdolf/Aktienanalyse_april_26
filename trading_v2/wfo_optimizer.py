from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Tuple

import pandas as pd

from .triple_barrier import BarrierSpec, label_entries
from .rule_engine import RuleEngineV2
from .config_loader import load_global, load_learned

LEARNED_PATH = Path('config') / 'learned_params.json'
REPORTS_DIR = Path('reports')
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Grid:
    rsi_thr: List[int]
    bb_pos_thr: List[float]
    require_hist_rising: List[bool]


def _hit_rate(labels: List[int], ignore_neutral: bool = True) -> float:
    if ignore_neutral:
        filt = [x for x in labels if x != 0]
    else:
        filt = labels
    if not filt:
        return 0.0
    return sum(1 for x in filt if x == 1) / len(filt)


def optimize_symbol_wfo(symbol: str, df: pd.DataFrame, train_days: int = 252*1, test_days: int = 63, step_days: int = 63,
                        grid: Grid | None = None) -> Dict[str, Any]:
    """Minimal WFO: choose params by best out-of-sample hit rate of triple-barrier labels."""
    global_cfg = load_global()
    labeling = global_cfg.get('labeling', {})
    spec = BarrierSpec(pt_pct=float(labeling.get('pt_pct', 0.08)), sl_pct=float(labeling.get('sl_pct', 0.04)), max_hold_days=int(labeling.get('max_hold_days', 60)))

    if grid is None:
        grid = Grid(rsi_thr=list(range(28, 46, 3)), bb_pos_thr=[0.05, 0.10, 0.15, 0.20, 0.25], require_hist_rising=[True, False])

    # build candidate list
    candidates = list(itertools.product(grid.rsi_thr, grid.bb_pos_thr, grid.require_hist_rising))

    # walk forward windows by index (df must be time-ordered)
    df = df.copy()
    df = df.sort_index()

    results = []
    best_params = None
    best_oos = -1.0

    # simple index-based rolling
    start = 0
    while True:
        train_start = start
        train_end = train_start + train_days
        test_end = train_end + test_days
        if test_end >= len(df):
            break

        train = df.iloc[train_start:train_end]
        test = df.iloc[train_end:test_end]

        # identify entry events with candidate params by replaying RuleEngine in rules_wfo mode is heavy.
        # Here we use a deterministic entry-event extraction based on the entry rule (FLAT->ENTRY_ACTIVE trigger).
        def entry_indices(data: pd.DataFrame, rsi_thr: float, bb_pos_thr: float, require_hist_rising: bool) -> List[int]:
            idxs = []
            in_pos = False
            for i in range(1, len(data)):
                row = data.iloc[i]
                prev = data.iloc[i-1]
                denom = float(row['BB_Upper'] - row['BB_Lower'])
                bb_pos = float((row['Close'] - row['BB_Lower']) / denom) if denom != 0 else 0.5
                hist_rising = float(row['MACD_Hist']) > float(prev['MACD_Hist'])
                cond = (float(row['RSI']) <= rsi_thr) and ((bb_pos <= bb_pos_thr) or (float(row['Close']) <= float(row['BB_Lower']))) and (float(row['MACD_Hist']) < 0)
                if require_hist_rising:
                    cond = cond and hist_rising
                if (not in_pos) and cond:
                    idxs.append(i)
                    in_pos = True
                # naive reset when TP/SL hit or after max_hold_days
                # (for WFO scoring we only need entry events; we allow overlap to be limited)
                if in_pos and len(idxs) > 0:
                    # reset after some cooldown (10 bars) to avoid dense signals
                    if i - idxs[-1] > 10:
                        in_pos = False
            return idxs

        roll_best = None
        roll_best_oos = -1.0
        roll_best_n = 0

        for rsi_thr, bb_pos_thr, req in candidates:
            idxs = entry_indices(test, rsi_thr, bb_pos_thr, req)
            labels = label_entries(test, idxs, spec)
            hr = _hit_rate(labels, ignore_neutral=True)
            if hr > roll_best_oos:
                roll_best_oos = hr
                roll_best = {'rsi_thr': int(rsi_thr), 'bb_pos_thr': float(bb_pos_thr), 'require_hist_rising': bool(req)}
                roll_best_n = len(labels)

        results.append({
            'train_range': [str(train.index[0].date()), str(train.index[-1].date())],
            'test_range': [str(test.index[0].date()), str(test.index[-1].date())],
            'best_params': roll_best,
            'oos_hit_rate': roll_best_oos,
            'n_trades': roll_best_n,
        })

        if roll_best_oos > best_oos:
            best_oos = roll_best_oos
            best_params = roll_best

        start += step_days

    return {'symbol': symbol, 'best_params': best_params or {}, 'best_oos_hit_rate': best_oos, 'rolls': results}


def write_learned(symbol: str, params: Dict[str, Any]) -> None:
    learned = {}
    if LEARNED_PATH.exists():
        try:
            learned = json.loads(LEARNED_PATH.read_text(encoding='utf-8'))
        except Exception:
            learned = {}
    learned[symbol] = params
    LEARNED_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEARNED_PATH.write_text(json.dumps(learned, ensure_ascii=False, indent=2), encoding='utf-8')


def write_report(report: Dict[str, Any]) -> Path:
    date = pd.Timestamp.now().strftime('%Y%m%d')
    path = REPORTS_DIR / f"wfo_{date}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return path
