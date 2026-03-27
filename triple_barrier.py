from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List

LOG_DIR = Path('logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)


def write_daily_log(date: str, ticker: str, payload: Dict[str, Any]) -> None:
    """Write one JSON line per call."""
    path = LOG_DIR / f"signals_{date}.jsonl"
    record = {'date': date, 'ticker': ticker, **payload}
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + "
")
