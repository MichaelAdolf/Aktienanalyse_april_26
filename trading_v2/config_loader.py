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
    )


def resolve_params(symbol: str, mode: str, global_cfg: Dict[str, Any], learned: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve per-ticker params for RuleEngine according to mode."""
    # defaults
    params = {
        'rsi_thr': 35,
        'bb_pos_thr': 0.20,
        'require_hist_rising': False,
        'entry_window_days': 4,
        'validation_bonus': 15,
        'erosion_penalty': 8,
        'erosion_margin': 5,
    }
    profile = global_cfg.get("active_profile")
    if profile:
        from config_thresholds import PROFILES
        prof = PROFILES.get(profile, {})
        for block in ("ENTRY", "CONFIDENCE"):
            if block in prof:
                params.update(prof[block])
    # allow defining defaults in global.json (optional)
    defaults = (global_cfg.get('defaults') or {}) if isinstance(global_cfg, dict) else {}
    params.update({k: defaults[k] for k in params.keys() if k in defaults})

    if mode in ('rules_wfo', 'rules_wfo_meta'):
        sym = learned.get(symbol, {}) if isinstance(learned, dict) else {}
        for k in ('rsi_thr', 'bb_pos_thr', 'require_hist_rising'):
            if k in sym:
                params[k] = sym[k]
    return params
