
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

# Daten & Indikatoren aus deinem Projekt
from core_magic_3 import lade_daten_aktie, berechne_indikatoren

# WFO-Lerner (besteht bereits)
from trading_v2.wfo_optimizer import optimize_symbol_wfo, write_learned, write_report, Grid


@dataclass
class LearnResult:
    symbol: str
    best_params: Dict[str, Any]
    best_oos_hit_rate: float
    report_path: Optional[str] = None


def learn_symbol(
    symbol: str,
    period: str = "4y",
    train_days: int = 252,
    test_days: int = 63,
    step_days: int = 63,
    grid: Optional[Grid] = None,
    persist: bool = True,
    write_json_report: bool = True,
) -> LearnResult:
    """
    Lernt Entry-Parameter für RuleEngineV2 BUY-Events via WFO + Triple-Barrier Labels.
    Ergebnis ist kompatibel zu resolve_params(): rsi_thr, bb_pos_thr, require_hist_rising.

    - Lädt Daten
    - berechnet Indikatoren
    - führt optimize_symbol_wfo aus
    - schreibt learned_params.json (optional)
    - schreibt Report (optional)
    """
    df = lade_daten_aktie(symbol, period=period)
    df = berechne_indikatoren(df)

    report = optimize_symbol_wfo(
        symbol=symbol,
        df=df,
        train_days=train_days,
        test_days=test_days,
        step_days=step_days,
        grid=grid,
    )

    best_params = report.get("best_params", {}) or {}
    best_oos = float(report.get("best_oos_hit_rate", 0.0))

    rep_path = None
    if persist:
        write_learned(symbol, best_params)
    if write_json_report:
        rep_path = str(write_report(report))

    return LearnResult(
        symbol=symbol,
        best_params=best_params,
        best_oos_hit_rate=best_oos,
        report_path=rep_path,
    )


def learn_watchlist(
    symbols: List[str],
    period: str = "4y",
    train_days: int = 252,
    test_days: int = 63,
    step_days: int = 63,
    grid: Optional[Grid] = None,
    persist: bool = True,
    write_json_report: bool = True,
) -> List[LearnResult]:
    """
    Batch-Learning für mehrere Symbole (z.B. Watchlist).
    """
    results: List[LearnResult] = []
    for sym in symbols:
        try:
            res = learn_symbol(
                symbol=sym,
                period=period,
                train_days=train_days,
                test_days=test_days,
                step_days=step_days,
                grid=grid,
                persist=persist,
                write_json_report=write_json_report,
            )
            results.append(res)
        except Exception as e:
            # bewusst robust: ein Symbol darf nicht den Batch killen
            results.append(
                LearnResult(
                    symbol=sym,
                    best_params={},
                    best_oos_hit_rate=0.0,
                    report_path=f"ERROR: {type(e).__name__}: {e}",
                )
            )
    return results
