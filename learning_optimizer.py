
from __future__ import annotations
import itertools, json
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from pathlib import Path

# --- Projekt-Imports (nutzen deine vorhandenen Funktionen/Analyzer) ---
from core_magic_3 import lade_daten_aktie, berechne_indikatoren, lade_fundamentaldaten  # [3](https://www.nasdaq.com/articles/10-top-growth-stocks-2026)
from config.thresholds import get_thresholds, load_learned, save_learned                # wird in Schritt 1 bereitgestellt
from SwingtradingSignale import (                                                       # [2](https://www.investing.com/academy/stock-picks/top-ten-2026-stocks/)
    RSIAnalysis, MACDAnalysis, ADXAnalysis,
    MarketRegimeAnalysis, TradeDecisionEngine, TradeRiskManager
)

# ---------- 1) Suchräume: klein starten (Performance!) ----------
SEARCH_SPACE: Dict[str, List[Any]] = {
    "ADX.strong_trend": [24, 25, 27],
    "RSI.trend_bias":   [50, 52, 55],
    "ATR_MULTS.trend_market.sl": [1.2, 1.5],
    "ATR_MULTS.trend_market.tp": [2.0, 3.0],
}

# ---------- 2) Scoring-Funktion (Sharpe/CAGR mit Drawdown-Strafe) ----------
def _score_equity(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return -1e9
    ret = equity_curve.pct_change().dropna()
    if ret.empty or ret.std() == 0:
        return -1e9
    cagr = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (252/len(equity_curve)) - 1
    sharpe = np.sqrt(252) * (ret.mean() / (ret.std() + 1e-12))
    roll_max = equity_curve.cummax()
    dd = (equity_curve / roll_max) - 1.0
    maxdd = dd.min()  # negativ
    return 0.6 * sharpe + 0.4 * cagr + 0.5 * (maxdd)

# ---------- 3) Sehr einfacher Walk-Forward-Backtest (long-only, 1 Position) ----------
def _walk_forward(data: pd.DataFrame, thresholds: Dict[str, Any]) -> float:
    rsi = RSIAnalysis(
        oversold=thresholds["RSI"]["oversold"],
        overbought=thresholds["RSI"]["overbought"],
        bullish_floor=thresholds["RSI"]["bullish_floor"],
        bearish_ceiling=thresholds["RSI"]["bearish_ceiling"],
    )
    macd = MACDAnalysis()
    adx  = ADXAnalysis(
        weak_trend=thresholds["ADX"]["weak_trend"],
        strong_trend=thresholds["ADX"]["strong_trend"],
        extreme_trend=thresholds["ADX"]["extreme_trend"],
    )
    regime_an = MarketRegimeAnalysis()
    engine    = TradeDecisionEngine()

    equity = [10000.0]
    pos_price = None
    stop = tp = None
    closes = data["Close"]

    # starte konservativ ab Tag 60 (Indikatoren stabil)
    for i in range(max(60, len(data)//10), len(data)):
        window = data.iloc[:i+1]
        rsi_res = rsi.analyse(window)
        macd_res = macd.analyse(window)
        adx_res  = adx.analyse(window)
        ma_res   = {"ma_trend": "neutral", "ma_cross": "none"}  # reicht dem Regime-Analyzer
        market   = regime_an.analyse(rsi_res, macd_res, adx_res, ma_res)
        decision = engine.decide(market, rsi_res, macd_res, adx_res)  # nutzt deine bestehende Engine  [2](https://www.investing.com/academy/stock-picks/top-ten-2026-stocks/)

        price = float(closes.iloc[i])
        regime = market.get("market_regime", "default")
        mults = thresholds["ATR_MULTS"].get(regime, thresholds["ATR_MULTS"]["default"])

        if pos_price is None:
            if decision["action"] == "BUY":
                pos_price = price
                trm = TradeRiskManager(einstiegskurs=pos_price, regime=regime)
                sltp = trm.sl_tp_by_atr(
                    atr=float(window["ATR"].iloc[-1]),
                    position_typ="long",
                    mults=mults
                )
                stop, tp = sltp["stop_loss"], sltp["take_profit"]
            equity.append(equity[-1])
        else:
            # offene Position: auf SL/TP prüfen
            if price <= stop or price >= tp:
                pnl = (price - pos_price)
                equity.append(equity[-1] + pnl)
                pos_price, stop, tp = None, None, None
            else:
                equity.append(equity[-1])

    curve = pd.Series(equity, index=data.index[:len(equity)])
    return _score_equity(curve)

# ---------- 4) Kandidaten-Kombinationen aus dem Gitter ----------
def _product_space(search: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    keys = list(search.keys())
    vals = [search[k] for k in keys]
    combos = []
    for tpl in itertools.product(*vals):
        combo = {}
        for k, v in zip(keys, tpl):
            node, rest = k.split(".", 1)
            d = combo.setdefault(node, {})
            parts = rest.split(".")
            for p in parts[:-1]:
                d = d.setdefault(p, {})
            d[parts[-1]] = v
        combos.append(combo)
    return combos

# ---------- 5) Öffentliche API: Symbol optimieren & learned_params.json schreiben ----------
def optimize_symbol(symbol: str, period="4y") -> Dict[str, Any]:
    data = lade_daten_aktie(symbol, period=period)        # ✔️ robust mit Backoff/TTL  [3](https://www.nasdaq.com/articles/10-top-growth-stocks-2026)
    data = berechne_indikatoren(data)                     # berechnet ATR/RSI/MACD/... ✔️  [3](https://www.nasdaq.com/articles/10-top-growth-stocks-2026)
    sector = (lade_fundamentaldaten(symbol) or {}).get("sector", None)  # kann None sein  [3](https://www.nasdaq.com/articles/10-top-growth-stocks-2026)

    # Basiswerte: Defaults (+ Sector-Overrides), aber noch OHNE symbol-spezifisch Learned
    base = get_thresholds(symbol=None, sector=sector)

    best_score = -1e9
    best_delta: Dict[str, Any] = {}

    for candidate in _product_space(SEARCH_SPACE):
        # merge: base <- candidate (deep)
        cfg = json.loads(json.dumps(base))
        _merge(cfg, candidate)
        score = _walk_forward(data, cfg)
        if score > best_score:
            best_score, best_delta = score, candidate

    # Learned persistieren (nur die deltas, nicht das gesamte cfg)
    learned = load_learned()
    learned[symbol] = learned.get(symbol, {})
    _merge(learned[symbol], best_delta)
    save_learned(learned)

    return {"symbol": symbol, "best_score": float(best_score), "delta": best_delta}

def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
