# config/thresholds.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

# --------- 1) Systemweite Defaults (sinnvolle Startwerte) ----------
DEFAULTS: Dict[str, Any] = {
    "RSI": {
        "oversold": 30,
        "overbought": 70,
        "bullish_floor": 40,
        "bearish_ceiling": 60,
        "trend_bias": 50   # als Filter im Trendmarkt (RSI > 50 long / < 50 short)
    },
    "ADX": {
        "weak_trend": 20,
        "strong_trend": 25,
        "extreme_trend": 40
    },
    # ATR-Multiplikatoren für SL/TP je Regime (können später gelernt werden)
    "ATR_MULTS": {
        "trend_market":      {"sl": 1.5, "tp": 3.0},
        "range_market":      {"sl": 1.0, "tp": 1.5},
        "late_trend":        {"sl": 1.2, "tp": 1.8},
        "transition_phase":  {"sl": 1.2, "tp": 1.8},
        "default":           {"sl": 1.2, "tp": 1.8},
    },
    # Gewichtungen in einer kombinierten Score-Logik (optional)
    "WEIGHTS": {
        "RSI": 0.3, "MACD": 0.4, "ADX": 0.3
    }
}

# --------- 2) Sektor-Overrides (optional, start klein) ----------
SECTOR_OVERRIDES: Dict[str, Any] = {
    # Beispiel: Tech tendiert zu stärkeren Trends -> ADX_STRONG leicht höher
    "Technology": {
        "ADX": {"strong_trend": 27}
    },
    # Beispiel: Defensives Konsum -> RSI Overbought früher greifen lassen
    "Consumer Defensive": {
        "RSI": {"overbought": 65}
    }
}

# --------- 3) Gelernte Symbol-spezifische Overrides ----------
LEARNED_PATH = Path("config/learned_params.json")

def load_learned() -> Dict[str, Any]:
    if LEARNED_PATH.exists():
        try:
            return json.loads(LEARNED_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_learned(payload: Dict[str, Any]) -> None:
    LEARNED_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEARNED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

# --------- 4) Zusammenführen: Defaults -> Sector -> Learned(Symbol) ----------
def get_thresholds(symbol: str | None = None, sector: str | None = None) -> Dict[str, Any]:
    import copy
    cfg = copy.deepcopy(DEFAULTS)

    # Sektor-Overrides mergen
    if sector and sector in SECTOR_OVERRIDES:
        _merge(cfg, SECTOR_OVERRIDES[sector])

    # Gelernte Symbol-Overrides mergen
    if symbol:
        learned = load_learned()
        if learned.get(symbol):
            _merge(cfg, learned[symbol])

    return cfg

def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """Rekursives Merge: override --> base (in-place)."""
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v

# --- Strategie-Profile (relative Offsets, NICHT persistent) ---
PROFILES = {
    # ✅ Baseline – aktueller Algorithmus
    "Conservative": {
        "ENTRY": {
            "rsi_thr": 35,
            "bb_pos_thr": 0.20,
            "require_hist_rising": False,
            "entry_window_days": 4,
        },
        "CONFIDENCE": {
            "validation_bonus": 15,
            "erosion_penalty": 8,
            "erosion_margin": 5,
        }
    },

    # 🟡 moderat gelockert
    "Balanced": {
        "RSI": {"trend_bias": -6},
        "ADX": {"strong_trend": -2},
        "ENTRY": {
            "rsi_thr": 38,
            "bb_pos_thr": 0.25,
            "require_hist_rising": False,
            "entry_window_days": 5,
        },
        "CONFIDENCE": {
            "validation_bonus": 18,
            "erosion_penalty": 6,
            "erosion_margin": 6,
        }
    },

    # 🔴 klar aggressiver
    "Aggressive": {
        "RSI": {"trend_bias": -10},
        "ADX": {"strong_trend": -4},
        "ENTRY": {
            "rsi_thr": 40,
            "bb_pos_thr": 0.30,
            "require_hist_rising": False,
            "entry_window_days": 6,
        },
        "CONFIDENCE": {
            "validation_bonus": 22,
            "erosion_penalty": 4,
            "erosion_margin": 7,
        }
    },
}

def _clamp(x, lo, hi):
    return max(lo, min(hi, x))

def apply_profile(thr: Dict[str, Any], profile_name: str) -> Dict[str, Any]:
    """
    Wendet ein nicht-persistentes Profil (Conservative/Balanced/Aggressive) auf 'thr' an.
    - Modifiziert das übergebene Dict IN-PLACE (wie bei get_thresholds-Merge).
    - Wirkt NUR zur Laufzeit, ändert NICHT defaults/learned-Dateien.
    """
    profile = PROFILES.get(profile_name) or {}
    # Rekursiv mergen (wie bei _merge), aber mit "Offset-Logik" für Zahlen
    def _apply(base, patch):
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                _apply(base[k], v)
            else:
                # Zahlen-Offset (z. B. -2/+0.2) oder Override
                if isinstance(v, (int, float)) and isinstance(base.get(k), (int, float)):
                    new_val = base[k] + v
                    # einfache Schutzkorridore:
                    if k == "trend_bias":
                        new_val = _clamp(new_val, 40, 60)
                    if k == "strong_trend":
                        new_val = _clamp(new_val, 15, 40)
                    if k == "tp":
                        new_val = _clamp(new_val, 1.2, 3.5)
                    base[k] = new_val
                else:
                    base[k] = v
    _apply(thr, profile)
    return thr
