from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any

STATE_PATH = Path('config') / 'runtime_state.json'

@dataclass
class TradeState:
    state: str = 'FLAT'
    entry_day: str | None = None
    entry_price: float | None = None
    confidence: float = 0.0
    last_signal_day: str | None = None


def load_all() -> Dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_all(payload: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def load_state(symbol: str) -> TradeState:
    raw = load_all().get(symbol, {})
    if not isinstance(raw, dict):
        return TradeState()
    return TradeState(**{k: raw.get(k) for k in TradeState.__dataclass_fields__.keys()})


def save_state(symbol: str, st: TradeState) -> None:
    all_ = load_all()
    all_[symbol] = asdict(st)
    save_all(all_)
