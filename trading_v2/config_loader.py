from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

ROOT = Path('.')

GLOBAL_PATH = ROOT / 'config' / 'global.json'
UI_POLICY_PATH = ROOT / 'config' / 'ui_policy.json'
LEARNED_PATH = ROOT / 'config' / 'learned_params.json'

@dataclass
class UiPolicy:
    mode: str
    meta_enabled: bool
    meta_threshold: float
    show_suppressed: bool
    active_profile: str

def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return default


def load_global() -> Dict[str, Any]:
    return _read_json(GLOBAL_PATH, {})


def load_learned() -> Dict[str, Any]:
    return _read_json(LEARNED_PATH, {})


def load_ui_policy() -> UiPolicy:
    raw = _read_json(UI_POLICY_PATH, {"mode": "rules_only", "meta": {"enabled": False, "threshold": 0.5, "show_suppressed": True}})
    meta = raw.get('meta', {}) if isinstance(raw, dict) else {}
    return UiPolicy(
        mode=str(raw.get('mode', 'rules_only')),
        meta_enabled=bool(meta.get('enabled', False)),
        meta_threshold=float(meta.get('threshold', 0.5)),
        show_suppressed=bool(meta.get('show_suppressed', True)),
        active_profile=str(raw.get('active_profile', 'Conservative')),
    )



def resolve_params(symbol: str, mode: str, global_cfg: Dict[str, Any], learned: Dict[str, Any], active_profile: str | None = None) -> Dict[str, Any]:
    """Resolve per-ticker params for RuleEngine according to mode."""
    global_cfg = global_cfg or {}

    # 1) Baseline Defaults (Conservative)
    params = {
        "rsi_thr": 35,
        "bb_pos_thr": 0.20,
        "require_hist_rising": False,
        "entry_window_days": 4,
        "validation_bonus": 15,
        "erosion_penalty": 8,
        "erosion_margin": 5,
    }

    # 2) Global lifecycle defaults aus global.json (wenn vorhanden)
    lifecycle = global_cfg.get("lifecycle", {}) if isinstance(global_cfg, dict) else {}
    params["entry_window_days"] = int(lifecycle.get("entry_window_days", params["entry_window_days"]))
    params["validation_bonus"] = float(lifecycle.get("validation_bonus", params["validation_bonus"]))
    params["erosion_penalty"] = float(lifecycle.get("erosion_penalty", params["erosion_penalty"]))
    params["erosion_margin"] = float(lifecycle.get("erosion_margin", params["erosion_margin"]))

    # 3) Learned pro Ticker (nur wenn Mode es erlaubt)
    if mode in ("rules_wfo", "rules_wfo_meta"):
        sym = learned.get(symbol, {}) if isinstance(learned, dict) else {}
        for k in ("rsi_thr", "bb_pos_thr", "require_hist_rising"):
            if k in sym:
                params[k] = sym[k]

    # 4) Profile IMMER ALS LETZTER SHIFT (garantiert sichtbarer Effekt)
    prof_name = active_profile or global_cfg.get("active_profile") or "Conservative"
    try:
        from trading_v2.config_thresholds import PROFILES  # wenn config_thresholds im Package liegt
    except Exception:
        from config_thresholds import PROFILES            # fallback, falls es im Root liegt

    prof = PROFILES.get(prof_name, {}) if isinstance(PROFILES, dict) else {}

    # Profile können absolute Werte liefern (empfohlen)
    for block in ("ENTRY", "CONFIDENCE"):
        if isinstance(prof, dict) and block in prof and isinstance(prof[block], dict):
            params.update(prof[block])

    return params
