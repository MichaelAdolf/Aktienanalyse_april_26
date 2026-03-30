from __future__ import annotations

import json
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pytz

# Projekt-Funktionen
from core_magic_3 import lade_aktien, lade_daten_aktie, berechne_indikatoren

# V2 Engine + Param Resolver
from trading_v2.rule_engine import RuleEngineV2
from trading_v2.config_loader import load_global, load_learned, load_ui_policy, resolve_params


# ----------------------------
# Konfiguration
# ----------------------------
PROFILE = "Aggressive"  # fest auf Aggressive, wie gewünscht
DEFAULT_PERIOD = "4y"   # für Trefferquote/Perioden
MAIL_SUBJECT_PREFIX = "Daily Trading Briefing"

# Periodenbewertung (wie im Dashboard): Auswertungstage & Mindestanstieg
EVAL_DAYS = int(os.getenv("EVAL_DAYS", "61"))
MIN_CHANGE = float(os.getenv("MIN_CHANGE", "0.08"))  # 8%
MAX_GAP_DAYS = int(os.getenv("MAX_GAP_DAYS", "5"))

# Auto-learned verwenden?
AUTO_LEARNED = os.getenv("AUTO_LEARNED", "1").strip() in ("1", "true", "True", "yes", "YES")

# SMTP via ENV (GitHub Secrets)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.web.de")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_TO = os.getenv("SMTP_TO", "")

# Zeitzone für "nur Mo-Fr um 06:00 senden"
LOCAL_TZ = os.getenv("LOCAL_TZ", "Europe/Berlin")


# ----------------------------
# Helper: Zeitfenster Mo-Fr 06:00 lokal
# ----------------------------
def should_send_now() -> bool:
    tz = pytz.timezone(LOCAL_TZ)
    now = datetime.now(tz)
    # Mo=0 .. So=6
    if now.weekday() > 4:
        return False
    return now.hour == 6


# ----------------------------
# Helper: Validierung Daten (letzte gültige Zeilen)
# ----------------------------
REQUIRED_COLS = ["RSI", "MACD_Hist", "ADX", "ATR", "BB_Upper", "BB_Lower", "Close"]


def last_valid_data(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.dropna(subset=[c for c in REQUIRED_COLS if c in df.columns]).copy()
    return out


# ----------------------------
# Entry-Events (Buy-Tage) nach Entry-Regel (wie im Dashboard-Entry)
# ----------------------------
def ruleengine_buy_days(
    df: pd.DataFrame,
    rsi_thr: float,
    bb_pos_thr: float,
    require_hist_rising: bool,
) -> List[pd.Timestamp]:
    buy_dates: List[pd.Timestamp] = []
    if df is None or df.empty:
        return buy_dates

    needed = ["Close", "BB_Upper", "BB_Lower", "RSI", "MACD_Hist"]
    if any(c not in df.columns for c in needed):
        return buy_dates

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]

        if any(pd.isna(row[c]) for c in needed):
            continue

        denom = float(row["BB_Upper"] - row["BB_Lower"])
        bb_pos = float((row["Close"] - row["BB_Lower"]) / denom) if denom != 0 else 0.5

        cond = (
            float(row["RSI"]) <= float(rsi_thr)
            and (
                bb_pos <= float(bb_pos_thr)
                or float(row["Close"]) <= float(row["BB_Lower"])
            )
            and float(row["MACD_Hist"]) < 0.0
        )

        if require_hist_rising:
            if pd.isna(prev["MACD_Hist"]):
                cond = False
            else:
                cond = cond and (float(row["MACD_Hist"]) > float(prev["MACD_Hist"]))

        if cond:
            buy_dates.append(df.index[i])

    return buy_dates


def cluster_periods_from_dates(dates: List[pd.Timestamp], max_gap_days: int = 5) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
    if not dates:
        return []
    dates = sorted(dates)
    periods: List[Tuple[pd.Timestamp, pd.Timestamp]] = []
    start = prev = dates[0]
    for d in dates[1:]:
        gap = (d - prev).days
        if gap <= max_gap_days:
            prev = d
        else:
            periods.append((start, prev))
            start = prev = d
    periods.append((start, prev))
    return periods


def evaluate_periods(
    periods: List[Tuple[pd.Timestamp, pd.Timestamp]],
    df: pd.DataFrame,
    eval_days: int,
    min_change: float
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    if df is None or df.empty:
        return pd.DataFrame(rows)

    for start, end in periods:
        if end not in df.index:
            continue
        end_idx = df.index.get_loc(end)
        entry_price = float(df["Close"].iloc[end_idx])

        lookahead_idx = end_idx + int(eval_days)
        if lookahead_idx >= len(df):
            rows.append({
                "Start": start,
                "Ende": end,
                "Signal": None,
                "Start_Kurs": round(entry_price, 4),
                "Max_Kurs": None,
                "Kurs_Diff": None,
                "Kommentar": "Periode noch nicht auswertbar (zu nah am Datenende)",
            })
            continue

        window = df["Close"].iloc[end_idx:lookahead_idx + 1]
        max_close = float(window.max())
        diff = (max_close - entry_price) / entry_price
        hit = diff >= float(min_change)

        rows.append({
            "Start": start,
            "Ende": end,
            "Signal": bool(hit),
            "Start_Kurs": round(entry_price, 4),
            "Max_Kurs": round(max_close, 4),
            "Kurs_Diff": round(diff, 4),
            "Kommentar": f"Max-Anstieg >= {min_change*100:.1f}%: {hit}",
        })

    return pd.DataFrame(rows)


def compute_hitrate(df: pd.DataFrame, params: Dict[str, Any]) -> Tuple[Optional[float], int]:
    buy_dates = ruleengine_buy_days(
        df,
        rsi_thr=float(params.get("rsi_thr", 35)),
        bb_pos_thr=float(params.get("bb_pos_thr", 0.20)),
        require_hist_rising=bool(params.get("require_hist_rising", False)),
    )
    periods = cluster_periods_from_dates(buy_dates, max_gap_days=MAX_GAP_DAYS)
    df_eval = evaluate_periods(periods, df, EVAL_DAYS, MIN_CHANGE)
    if df_eval is None or df_eval.empty:
        return None, 0

    df_done = df_eval[df_eval["Signal"].notna()].copy()
    if len(df_done) == 0:
        return None, 0

    hitrate = float(df_done["Signal"].mean()) * 100.0
    return round(hitrate, 2), int(len(df_done))


# ----------------------------
# Confidence Mapping (einfach & nutzerfreundlich)
# ----------------------------
def confidence_bucket(conf: float) -> str:
    # Heuristik passend zu deinem V2-Setup (validation_bonus ~15)
    if conf >= 20:
        return "hoch"
    if conf >= 10:
        return "mittel"
    return "niedrig"


# ----------------------------
# HTML Rendering
# ----------------------------
def render_table(rows: List[Dict[str, Any]], title: str) -> str:
    html = f"""
    <h2 style="font-family:Arial,sans-serif;">{title}</h2>
    <table cellpadding="6" cellspacing="0"
           style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px;width:100%;">
      <thead>
        <tr style="background-color:#f2f2f2;">
          <th align="left">Aktie</th>
          <th align="center">Signal</th>
          <th align="center">Confidence</th>
          <th align="center">Trefferquote</th>
        </tr>
      </thead>
      <tbody>
    """
    for r in rows:
        signal = r["signal"]
        bgcolor = ""
        if signal == "BUY":
            bgcolor = "background-color:#eaf6ee;"  # leicht grün
        elif signal == "SELL":
            bgcolor = "background-color:#f9ecec;"  # leicht rot (optional)
        # HOLD bleibt neutral

        sig_icon = "🟡"
        if signal == "BUY":
            sig_icon = "🟢"
        elif signal == "SELL":
            sig_icon = "🔴"
        elif signal == "HOLD":
            sig_icon = "⏸"

        hit = r["hitrate"]
        hit_txt = "–" if hit is None else f"<b>{hit:.0f} %</b>"

        html += f"""
        <tr style="{bgcolor}">
          <td><b>{r['name']}</b> ({r['symbol']})</td>
          <td align="center">{sig_icon} {signal}</td>
          <td align="center">{r['confidence_txt']}</td>
          <td align="center">{hit_txt}</td>
        </tr>
        """

    html += """
      </tbody>
    </table>
    """

    html += f"""
    <p style="font-family:Arial,sans-serif;font-size:12px;color:#666;margin-top:12px;">
      Profil: <b>{PROFILE}</b> · Auto(learned): <b>{'ON' if AUTO_LEARNED else 'OFF'}</b> ·
      Trefferquote basiert auf abgeschlossenen BUY-Perioden (Auswertung {EVAL_DAYS} Tage, Mindestanstieg {MIN_CHANGE*100:.1f}%).
    </p>
    """
    return html


# ----------------------------
# SMTP Send
# ----------------------------
def send_email(subject: str, html_body: str) -> None:
    sender = "mymichael.adolf@web.de"
    password = "H6PL52UHTMGTC4S2XHO7"
    #password = os.environ.get("LIJ22ZIUJO6SEDKQUDORE")  # Passwort besser über Secrets sichern
    recipient = "mymichael.adolf@web.de"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    # STARTTLS auf Port 587
    with smtplib.SMTP("smtp.web.de", 587) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

def send_email(subject, html_body):
    sender = "mymichael.adolf@web.de"
    password = "H6PL52UHTMGTC4S2XHO7"
    #password = os.environ.get("LIJ22ZIUJO6SEDKQUDORE")  # Passwort besser über Secrets sichern
    recipient = "mymichael.adolf@web.de"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    # STARTTLS auf Port 587
    with smtplib.SMTP("smtp.web.de", 587) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

# ----------------------------
# Main
# ----------------------------
def main() -> None:
    # Optional: nur senden, wenn lokal Mo-Fr 06:xx
    # (hilft bei GitHub Actions DST, wenn du 2 Cron-Zeiten nutzt)
    if os.getenv("ENFORCE_6AM_LOCAL", "1").strip() in ("1", "true", "True"):
        if not should_send_now():
            return

    watchlist = lade_aktien()
    if not watchlist:
        return

    # Parameter Resolver vorbereiten (Aggressive)
    global_cfg = load_global()
    policy = load_ui_policy()
    global_cfg["active_profile"] = PROFILE
    learned = load_learned() if AUTO_LEARNED else {}

    engine = RuleEngineV2()
    # Engine intern konfigurieren (Profile/Learned)
    engine.global_cfg["active_profile"] = PROFILE
    if not AUTO_LEARNED:
        engine.learned = {}

    rows: List[Dict[str, Any]] = []

    for w in watchlist:
        name = w.get("name", "")
        symbol = w.get("symbol", "")
        if not symbol:
            continue

        try:
            df_raw = lade_daten_aktie(symbol, period=DEFAULT_PERIOD)
            df_raw = berechne_indikatoren(df_raw)
            df = last_valid_data(df_raw)
            if df is None or df.empty:
                raise ValueError("Keine validen Kursdaten")

            # V2 Signal
            decision = engine.evaluate(symbol, df)
            signal = decision.signal
            conf_txt = confidence_bucket(float(decision.confidence))

            # Entry-Params für Aggressive (+ learned, wenn ON)
            params = resolve_params(
                symbol=symbol,
                mode=policy.mode,
                global_cfg=global_cfg,
                learned=learned,
                active_profile=PROFILE,
            )

            # Trefferquote
            hitrate, n_done = compute_hitrate(df, params)

            rows.append({
                "name": name,
                "symbol": symbol,
                "signal": signal,
                "confidence_txt": conf_txt,
                "hitrate": hitrate,
                "n_done": n_done,
            })

        except Exception as e:
            rows.append({
                "name": name,
                "symbol": symbol,
                "signal": "HOLD",
                "confidence_txt": "–",
                "hitrate": None,
                "n_done": 0,
            })

    today_local = datetime.now(pytz.timezone(LOCAL_TZ)).strftime("%d.%m.%Y")
    subject = f"{MAIL_SUBJECT_PREFIX} – {PROFILE} – {today_local}"
    html = render_table(rows, f"📈 Watchlist – {PROFILE} Profil")

    send_email(subject, html)


if __name__ == "__main__":
    main()
