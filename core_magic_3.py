from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import plotly.graph_objects as go
from ta.trend import ADXIndicator
from ta.momentum import StochasticOscillator
import json
from pathlib import Path
import time
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
import urllib.request
import xml.etree.ElementTree as ET


# ------------------------------------------------------
# Aktien aus der definierten Watchlist laden
# ------------------------------------------------------
@st.cache_data(show_spinner=False)
def lade_aktien(pfad="Watchlist.json"):
    file = Path(pfad)
    if not file.exists():
        st.warning(f"Datei {pfad} wurde nicht gefunden.")
        return []

    with open(file, "r", encoding="utf-8") as f:
        raw = json.load(f)

    aktien = []
    for entry in raw:
        if isinstance(entry, dict):
            aktien.append(entry)
        elif isinstance(entry, (list, tuple)) and len(entry) == 2:
            aktien.append({"name": entry[0], "symbol": entry[1]})
        else:
            st.warning(f"Unbekanntes Format in Watchlist: {entry}")

    aktien.sort(key=lambda x: x["name"].lower())
    return aktien

# ------------------------------------------------------
# Erweitern der Watchlist
# ------------------------------------------------------
def save_watchlist_json(watchlist, pfad="Watchlist.json"):
    file = Path(pfad)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)



# ------------------------------------------------------
# Lade Daten
# ------------------------------------------------------
@st.cache_data(show_spinner=False)
@st.cache_data(show_spinner=False, ttl=60*15)  # 15 Minuten Cache
def lade_daten_aktie(symbol: str, period="3y") -> pd.DataFrame:
    """
    Robuster Loader mit Retry/Backoff gegen Rate-Limits.
    Cache via Streamlit: 15 Min TTL.
    """
    max_retries = 5
    backoff_sec = 2.0
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            ticker = yf.Ticker(symbol)
            # Timeout-Guard: yfinance hat keinen expliziten Timeout-Param,
            # aber ein seltener Hänger kommt vor; wir halten nur Backoff/Retry bereit.
            data = ticker.history(period=period)

            # Fallback: manche Symbole liefern leer für lange Perioden
            if data is None or data.empty:
                # Probiere einen kürzeren Zeitraum, um temporär wenigstens etwas zu zeigen
                if period != "1y":
                    data = ticker.history(period="1y")
            if data is not None and not data.empty:
                return data

            # Wenn leer, als Fehler behandeln, damit Retry greift
            raise ValueError(f"Keine Daten für {symbol} (period={period}) erhalten.")

        except Exception as e:
            last_exception = e
            # Bei Rate-Limit oder Netzfehlern mit Backoff erneut
            time.sleep(backoff_sec)
            backoff_sec *= 1.8  # exponentiell

    # Nach max_retries: sauberes Fehlersignal
    raise RuntimeError(
        f"Fehler beim Laden von {symbol} nach {max_retries} Versuchen: {last_exception}"
    )

# ------------------------------------------------------
# Lade Fundamentaldaten
# ------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=60*60)  # 60 Minuten Cache
def lade_fundamentaldaten(ticker_symbol):
    max_retries, backoff = 4, 2.0
    last_exc = None
    for _ in range(max_retries):
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            fundamentaldaten = {
                "sector": info.get("sector", "Unknown"),
                "kgv": info.get("trailingPE"),
                "forward_kgv": info.get("forwardPE"),
                "kuv": info.get("priceToSalesTrailing12Months"),
                "kbv": info.get("priceToBook"),
                "marge": info.get("profitMargins"),
                "beta": info.get("beta"),
                "roe": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "Dividendenrendite": info.get("dividendYield", "N/A"),
                "Marktkapitalisierung": info.get("marketCap", "N/A"),
                "Gewinn je Aktie (EPS)": info.get("trailingEps", "N/A")
            }
            # Optional: Formatieren der Werte
            if fundamentaldaten["Dividendenrendite"] != "N/A":
                fundamentaldaten["Dividendenrendite (%)"] = fundamentaldaten.pop("Dividendenrendite") * 100
            if fundamentaldaten["Marktkapitalisierung"] != "N/A":
                mkt = fundamentaldaten["Marktkapitalisierung"]
                if isinstance(mkt, (int, float)):
                    if mkt > 1e12:
                        fundamentaldaten["Marktkapitalisierung"] = f"{mkt / 1e12:.2f} Bio."
                    elif mkt > 1e9:
                        fundamentaldaten["Marktkapitalisierung"] = f"{mkt / 1e9:.2f} Mrd."
                    elif mkt > 1e6:
                        fundamentaldaten["Marktkapitalisierung"] = f"{mkt / 1e6:.2f} Mio."
            return fundamentaldaten
        except Exception as e:
            last_exc = e
            time.sleep(backoff)
            backoff *= 1.8
    # Fallback: gib leere/Unknown-Werte zurück statt harten Abbruch
    st.warning(f"Fundamentaldaten für {ticker_symbol} derzeit nicht verfügbar: {last_exc}")
    return {
        "sector": "Unknown", "kgv": None, "forward_kgv": None, "kuv": None,
        "kbv": None, "marge": None, "beta": None, "roe": None,
        "debt_to_equity": None, "revenue_growth": None, "earnings_growth": None,
        "Dividendenrendite": "N/A", "Marktkapitalisierung": "N/A", "Gewinn je Aktie (EPS)": "N/A"
    }


def erklaere_fundamentales_umfeld(fundamentaldaten: dict) -> str:
    """
    Beschreibt das fundamentale Unternehmensumfeld auf Basis verfügbarer Kennzahlen.

    WICHTIG:
    - Rein beschreibend, nicht bewertend
    - Keine Handlungsempfehlung
    - Kein Einfluss auf Handelssignale oder Profile
    """

    texte = []

    # Wachstum / Reifegrad
    revenue_growth = fundamentaldaten.get("revenue_growth")
    if revenue_growth is not None:
        if revenue_growth > 0.10:
            texte.append(
                "Das Unternehmen zeigt im betrachteten Zeitraum ein erhöhtes Umsatzwachstum, "
                "was auf ein wachstumsorientiertes Unternehmensumfeld hindeutet."
            )
        elif revenue_growth > 0:
            texte.append(
                "Das Unternehmen weist moderates Umsatzwachstum auf, was auf ein eher "
                "etabliertes, aber weiterhin expandierendes Umfeld schließen lässt."
            )
        else:
            texte.append(
                "Die Umsätze entwickeln sich stagnierend oder rückläufig, was auf ein "
                "reiferes oder herausforderndes Unternehmensumfeld hinweist."
            )

    # Profitabilität
    profit_margin = fundamentaldaten.get("profit_margin")
    if profit_margin is not None:
        if profit_margin > 0.20:
            texte.append(
                "Die Profitabilität liegt auf einem vergleichsweise hohen Niveau, "
                "was auf effiziente Kostenstrukturen oder Preissetzungsmacht hindeutet."
            )
        elif profit_margin > 0:
            texte.append(
                "Die Profitabilität bewegt sich im moderaten Bereich und spiegelt "
                "ein ausgeglichenes Verhältnis zwischen Ertrag und Kosten wider."
            )
        else:
            texte.append(
                "Die Profitabilität ist gering oder negativ, was auf erhöhte Kosten, "
                "Investitionsphasen oder strukturelle Belastungen hindeuten kann."
            )

    # Verschuldung / Kapitalstruktur
    debt_ratio = fundamentaldaten.get("debt_ratio")
    if debt_ratio is not None:
        if debt_ratio > 0.6:
            texte.append(
                "Die Kapitalstruktur ist vergleichsweise fremdkapitallastig, "
                "was auf eine stärkere Abhängigkeit von externem Kapital hinweist."
            )
        elif debt_ratio > 0.3:
            texte.append(
                "Die Kapitalstruktur zeigt ein ausgewogenes Verhältnis zwischen "
                "Eigen- und Fremdkapital."
            )
        else:
            texte.append(
                "Die Kapitalstruktur ist überwiegend eigenkapitalbasiert, "
                "was auf eine solide finanzielle Basis hindeutet."
            )

    if not texte:
        texte.append(
            "Das fundamentale Unternehmensumfeld konnte auf Basis der verfügbaren "
            "Kennzahlen nicht eindeutig beschrieben werden."
        )

    texte.append(
        "Hinweis: Diese Darstellung beschreibt grundlegende Eigenschaften des "
        "Unternehmensumfelds auf Basis veröffentlichter Kennzahlen. "
        "Sie stellt keine Bewertung der Aktie dar und hat keinen Einfluss "
        "auf Handelssignale."
    )

    return "\n\n".join(texte)



# ==============================
# NEWS / STIMMUNGS-ANALYSE (Google News RSS + Kontext)
# ==============================

# Schlüsselwörter: bewusst simpel + erklärbar (DE + EN)
_POS_WORDS = {
    # EN
    "beat", "beats", "strong", "growth", "record", "approval", "expansion", "upgrade",
    "partnership", "surge", "rally", "outperform", "raises", "profit", "wins",
    # DE
    "stark", "wachstum", "rekord", "genehmigung", "zulassung", "ausbau", "hochgestuft",
    "kooperation", "partnerschaft", "übertrifft", "gewinn", "steigt", "erhöht", "auftrag",
}

_NEG_WORDS = {
    # EN
    "warning", "downgrade", "investigation", "lawsuit", "decline", "cut", "loss",
    "weak", "miss", "misses", "plunge", "fraud", "probe", "recall", "delay",
    # DE
    "gewinnwarnung", "herabstufung", "ermittlung", "klage", "rückgang", "senkt",
    "verlust", "schwach", "verfehlt", "einbruch", "rückruf", "warnung", "verzögerung",
}

# ✅ Finalisierte Kontextliste (9 Archetypen)
_CONTEXT_PATTERNS = {
    "STRATEGIC_WIN": [
        "deal", "contract", "agreement", "partnership", "award", "data center",
        "auftrag", "vertrag", "kooperation", "partnerschaft", "deal mit",
    ],
    "INDEX_INCLUSION": [
        "joined the s&p", "added to the s&p", "s&p 100", "s&p100", "index inclusion",
        "aufnahme in", "index", "dax", "mdax", "sdax", "stoxx",
    ],
    "EARNINGS_EVENT": [
        "earnings", "results", "guidance", "q1", "q2", "q3", "q4",
        "quartal", "quartalszahlen", "ergebnisse", "ausblick", "prognose",
    ],
    "LATE_STAGE_RUN": [
        "tripled", "has tripled", "up ", "%", "rally", "after a run", "after rally",
        "vervielfacht", "verdreifacht", "anstieg", "innerhalb eines jahres", "innerhalb eines Jahres",
    ],
    "VALUATION_DISCUSSION": [
        "still a buy", "is it too late", "too late", "valuation", "expensive", "priced in",
        "zu spät", "zu spaet", "noch kaufen", "bewertung", "teuer", "eingepreist",
    ],
    "OPERATIONAL_ISSUES": [
        "production", "outage", "shutdown", "quality", "supply", "delay",
        "produktion", "ausfall", "störung", "qualitäts", "liefer", "verzöger",
    ],
    "REGULATORY_PRESSURE": [
        "regulator", "antitrust", "sec", "doj", "fda", "probe", "investigation",
        "regulier", "kartell", "aufsicht", "ermittlung",
    ],
    "LEGAL_RISK": [
        "lawsuit", "litigation", "settlement", "fine", "penalty",
        "klage", "prozess", "vergleich", "strafe", "bußgeld", "bussgeld",
    ],
    "FINANCIAL_STRESS": [
        "debt", "liquidity", "cash burn", "refinance", "credit", "downgrade",
        "verschuld", "liquidität", "cashburn", "refinanz", "kredit", "herabstuf",
    ],
}

# Prioritäten: damit die wichtigsten Kontexte zuerst erscheinen
_CONTEXT_PRIORITY = [
    "REGULATORY_PRESSURE", "LEGAL_RISK", "FINANCIAL_STRESS", "OPERATIONAL_ISSUES",
    "EARNINGS_EVENT", "STRATEGIC_WIN", "INDEX_INCLUSION", "VALUATION_DISCUSSION", "LATE_STAGE_RUN",
]

# Textbausteine für die Erklärung (kurz & verständlich)
_CONTEXT_EXPLAIN = {
    "STRATEGIC_WIN": "Strategische/kommerzielle Meldungen (z. B. Deal/Vertrag/Partnerschaft) stehen im Fokus.",
    "INDEX_INCLUSION": "Index-/Aufnahme-Themen (z. B. S&P/DAX) werden diskutiert.",
    "EARNINGS_EVENT": "Quartalszahlen/Ausblick sind ein wiederkehrendes Thema.",
    "LATE_STAGE_RUN": "Starker vorheriger Kurslauf wird thematisiert (z. B. stark gestiegen/vervielfacht/Prozentangaben).",
    "VALUATION_DISCUSSION": "Ein Teil der Berichte dreht sich um Bewertung/Timing (z. B. ‚zu spät?‘ / ‚noch kaufen?‘).",
    "OPERATIONAL_ISSUES": "Hinweise auf operative Themen (Produktion/Lieferkette/Verzögerungen) tauchen auf.",
    "REGULATORY_PRESSURE": "Regulatorische/aufsichtsrechtliche Themen werden erwähnt.",
    "LEGAL_RISK": "Rechtliche Risiken (Klagen/Strafen) werden angesprochen.",
    "FINANCIAL_STRESS": "Finanzielle Anspannung (Verschuldung/Liquidität/Herabstufung) wird thematisiert.",
}


def _normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _extract_contexts(items: list[dict], max_contexts: int = 3) -> list[str]:
    """
    Ermittelt 0..n Kontexte aus Headlines+Descriptions:
    - zählt Treffer pro Kontext
    - gibt die Top-Kontexte nach Count + Priority zurück
    """
    counts = {k: 0 for k in _CONTEXT_PATTERNS.keys()}

    for it in items:
        title = _normalize_text(it.get("title", ""))
        desc = _normalize_text(it.get("description", ""))
        text = f"{title} {desc}".strip()

        for ctx, pats in _CONTEXT_PATTERNS.items():
            if any(p in text for p in pats):
                counts[ctx] += 1

    active = {k: v for k, v in counts.items() if v > 0}
    if not active:
        return []

    prio = {k: i for i, k in enumerate(_CONTEXT_PRIORITY)}
    items_sorted = sorted(active.items(), key=lambda kv: (-kv[1], prio.get(kv[0], 999)))
    return [k for k, _ in items_sorted[:max_contexts]]


def _classify_sentiment(items: list[dict]) -> tuple[str, int, int]:
    """
    Basissentiment (V1): zählt positive/negative Trigger.
    Ergebnis:
      - NEGATIV wenn neg > pos und neg>0
      - POSITIV wenn pos > neg und pos>0
      - sonst NEUTRAL
    """
    pos = 0
    neg = 0
    for it in items:
        title = _normalize_text(it.get("title", ""))
        desc = _normalize_text(it.get("description", ""))
        text = f"{title} {desc}".strip()

        if any(w in text for w in _POS_WORDS):
            pos += 1
        if any(w in text for w in _NEG_WORDS):
            neg += 1

    if neg > pos and neg > 0:
        return "NEGATIV", pos, neg
    if pos > neg and pos > 0:
        return "POSITIV", pos, neg
    return "NEUTRAL", pos, neg


def _compose_explanation(sentiment: str, contexts: list[str]) -> str:
    """
    Kombiniert Basissentiment + Kontextbausteine zu einem verständlichen Satz.
    """
    base = {
        "POSITIV": "Aktuelle Berichte wirken überwiegend konstruktiv bzw. unterstützend.",
        "NEGATIV": "Mehrere aktuelle Berichte enthalten Warnsignale oder Gegenwind.",
        "NEUTRAL": "Gemischte oder wenig dominante Nachrichtenlage – kein klarer Überhang erkennbar.",
    }.get(sentiment, "Nachrichtenlage aktuell schwer einzuordnen.")

    if not contexts:
        return base

    ctx_texts = []
    for c in contexts:
        t = _CONTEXT_EXPLAIN.get(c)
        if t:
            ctx_texts.append(t)

    if not ctx_texts:
        return base

    return base + " " + " ".join(ctx_texts)


def _fetch_google_news_rss(symbol: str, days: int = 7, limit: int = 12) -> list[dict]:
    """
    Holt Headlines aus Google News RSS (kostenlos, kein API-Key).
    Wir nutzen Suchfeed: https://news.google.com/rss/search?q=...
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return []

    base = symbol.split(".")[0]
    keyword = "Aktie" if symbol.endswith(".DE") else "stock"
    query = quote_plus(f"{base} {symbol} {keyword}")

    hl = os.getenv("NEWS_RSS_HL", "de")
    gl = os.getenv("NEWS_RSS_GL", "DE")
    ceid = os.getenv("NEWS_RSS_CEID", "DE:de")

    url = f"https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}"
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AktienanalyseBot/1.0)",
                "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_bytes = resp.read()

        root = ET.fromstring(xml_bytes)
        channel = root.find("channel")
        if channel is None:
            return []

        out: list[dict] = []
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            desc = (item.findtext("description") or "").strip()
            src_el = item.find("source")
            src = (src_el.text.strip() if src_el is not None and src_el.text else "").strip()

            keep = True
            if pub:
                try:
                    dt = parsedate_to_datetime(pub)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    keep = dt >= cutoff
                except Exception:
                    keep = True

            if not keep:
                continue

            if title:
                out.append({
                    "title": title,
                    "description": desc,
                    "url": link,
                    "source": src,
                    "published_at": pub,
                })

        # Duplikate nach Titel entfernen
        seen = set()
        dedup = []
        for it in out:
            t = it.get("title", "")
            if not t or t in seen:
                continue
            seen.add(t)
            dedup.append(it)

        return dedup[: int(limit)]

    except Exception:
        return []


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)  # 6h Cache
def lade_aktien_stimmung(symbol: str, days: int = 7, limit: int = 12) -> dict:
    """
    Liefert Stimmung + Kontext für eine Aktie.

    Rückgabe:
    {
      "sentiment": "POSITIV" | "NEUTRAL" | "NEGATIV",
      "contexts": list[str],
      "explanation": str,
      "pos_hits": int,
      "neg_hits": int,
      "headlines": list[dict],
      "as_of": "YYYY-MM-DD"
    }
    """
    as_of = datetime.now().strftime("%Y-%m-%d")

    items = _fetch_google_news_rss(symbol, days=days, limit=limit)
    if not items:
        return {
            "sentiment": "NEUTRAL",
            "contexts": [],
            "explanation": "Keine aktuellen News gefunden oder Quelle aktuell nicht erreichbar.",
            "pos_hits": 0,
            "neg_hits": 0,
            "headlines": [],
            "as_of": as_of,
        }

    sentiment, pos_hits, neg_hits = _classify_sentiment(items)
    contexts = _extract_contexts(items, max_contexts=3)
    explanation = _compose_explanation(sentiment, contexts)

    return {
        "sentiment": sentiment,
        "contexts": contexts,
        "explanation": explanation,
        "pos_hits": pos_hits,
        "neg_hits": neg_hits,
        "headlines": items,
        "as_of": as_of,
    }

def klassifiziere_aktie(symbol, data, fundamentaldaten):
    """
    Klassifiziert die Aktie ohne weitere Netzwerkaufrufe:
    - nutzt nur 'fundamentaldaten' (ggf. leer/Unknown) und 'data'
    - berechnet Volatilität & Momentum aus Kursdaten
    """

    # --- 1) Stammdaten/Grundlagen aus 'fundamentaldaten' (keine yfinance-Calls hier!)
    sector   = fundamentaldaten.get("sector")                # z.B. "Technology" oder "Unknown"
    industry = fundamentaldaten.get("industry")              # kann fehlen -> None

    # Marketcap best-effort aus Fundamentaldaten (kann formatiert sein: "1.23 Mrd.")
    marketcap = None
    mkt_raw = fundamentaldaten.get("Marktkapitalisierung")
    if isinstance(mkt_raw, (int, float)):
        marketcap = mkt_raw
    elif isinstance(mkt_raw, str):
        import re
        txt = mkt_raw.replace(" ", "")
        nums = re.findall(r"[0-9]+(?:[.,][0-9]+)?", txt)
        if nums:
            val = float(nums[0].replace(",", "."))
            if "Bio" in txt:
                marketcap = val * 1e12
            elif "Mrd" in txt:
                marketcap = val * 1e9
            elif "Mio" in txt:
                marketcap = val * 1e6

    # Bewertungs-/Wachstums-Kennzahlen aus 'lade_fundamentaldaten' (kleingeschriebene Keys!)
    kgv    = fundamentaldaten.get("kgv")
    div    = fundamentaldaten.get("Dividendenrendite (%)")   # wurde dort bereits in % umgerechnet
    umsatz = fundamentaldaten.get("revenue_growth")
    gewinn = fundamentaldaten.get("earnings_growth")

    # --- 2) Volatilität & Momentum aus Kursdaten
    if "ATR" in data.columns and len(data) > 20:
        volatilitaet = data["ATR"].iloc[-1] / max(1e-9, data["Close"].iloc[-1])
    else:
        volatilitaet = 0.02  # konservativer Fallback

    if len(data) > 20:
        momentum_20 = (data["Close"].iloc[-1] - data["Close"].iloc[-20]) / data["Close"].iloc[-20]
    else:
        momentum_20 = 0.0

    # --- 3) Scoring
    profil_scores = {"Growth": 0, "Value": 0, "Zyklisch": 0, "Defensiv": 0}
    trading_scores = {"Volatil": 0, "Momentum": 0}

    # Growth
    if umsatz and umsatz > 0.10: profil_scores["Growth"] += 2
    if gewinn and gewinn > 0.10: profil_scores["Growth"] += 2
    if volatilitaet > 0.03:      profil_scores["Growth"] += 1
    if sector in ["Technology", "Consumer Cyclical"]: profil_scores["Growth"] += 1
    if momentum_20 > 0.10:       profil_scores["Growth"] += 1

    # Value
    if kgv and kgv < 15:         profil_scores["Value"] += 2
    if div and div > 2:          profil_scores["Value"] += 1
    if volatilitaet < 0.02:      profil_scores["Value"] += 1
    if sector in ["Financial Services", "Industrial"]: profil_scores["Value"] += 1

    # Zyklisch (vereinheitliche Sektornamen bei Bedarf)
    if sector in ["Automobil", "Automotive", "Industrials", "Materials"]:
        profil_scores["Zyklisch"] += 2
    if volatilitaet > 0.025:
        profil_scores["Zyklisch"] += 1

    # Defensiv
    if sector in ["Healthcare", "Utilities", "Consumer Defensive"]:
        profil_scores["Defensiv"] += 2
    if volatilitaet < 0.018:
        profil_scores["Defensiv"] += 1
    if div and div > 2.5:
        profil_scores["Defensiv"] += 1

    # Trading-Status
    if volatilitaet > 0.05:          trading_scores["Volatil"] += 3
    if marketcap and marketcap < 2e9: trading_scores["Volatil"] += 2
    if momentum_20 > 0.15:           trading_scores["Momentum"] += 2
    if momentum_20 > 0.25:           trading_scores["Momentum"] += 2
    if volatilitaet > 0.03:          trading_scores["Momentum"] += 1

    # --- 4) Ergebnis
    max_profil = max(profil_scores.values()) if profil_scores else 0
    profil = "Keine" if max_profil == 0 else max(profil_scores, key=profil_scores.get)

    max_trading = max(trading_scores.values()) if trading_scores else 0
    trading_status = "Keine" if max_trading == 0 else max(trading_scores, key=trading_scores.get)

    return {
        "Sektor": sector,
        "Industrie": industry,
        "Profil": profil,
        "Trading_Status": trading_status,
        "Profil_Scores": profil_scores,
        "Trading_Scores": trading_scores
    }


def lade_analystenbewertung(symbol):
    ticker = yf.Ticker(symbol)
    anal_data = {}

    # Analysten-Empfehlungen (Buy/Hold/Sell)
    try:
        summary = ticker.recommendations_summary
        # Falls summary nicht None und kein DataFrame, versuche Umwandlung
        if summary is not None and not isinstance(summary, pd.DataFrame):
            summary = pd.DataFrame(summary)
        anal_data["summary"] = summary
    except Exception as e:
        anal_data["summary"] = None

    # Historische Empfehlungen
    try:
        recs = ticker.recommendations
        if recs is not None and not isinstance(recs, pd.DataFrame):
            recs = pd.DataFrame(recs)
        anal_data["recommendations"] = recs
    except Exception as e:
        anal_data["recommendations"] = None

    # Tiefere Analyse wie Wachstum/Kennzahlen
    try:
        analysis = ticker.analysis
        if analysis is not None and not isinstance(analysis, pd.DataFrame):
            analysis = pd.DataFrame(analysis)
        anal_data["analysis"] = analysis
    except Exception as e:
        anal_data["analysis"] = None

    return anal_data

def erklaere_kategorien(profil: str, trading_status: str) -> str:
    """
    Gibt eine rein beschreibende Charakterisierung des Marktverhaltens
    und des Handelsumfelds einer Aktie zurück.

    WICHTIG:
    - Die Texte sind rein informativ.
    - Sie stellen keine Bewertung und keine Handlungsempfehlung dar.
    - Sie haben keinen Einfluss auf Handelssignale oder die RuleEngine.

    Argumente:
    - profil: String, z.B. "Growth, Zyklisch"
    - trading_status: String, z.B. "Momentum, Volatil"

    Rückgabe:
    - String mit erklärenden, nicht-normativen Texten.
    """

    texte = {
        "Growth": (
            "Die Aktie zeigt im betrachteten Zeitraum Merkmale eines wachstumsorientierten "
            "Marktverhaltens. Solche Werte sind häufig durch erhöhte Investitionstätigkeit, "
            "stärkere Kursreaktionen auf Nachrichten und eine höhere Sensitivität gegenüber "
            "Marktstimmung gekennzeichnet."
        ),
        "Value": (
            "Die Aktie weist Merkmale eines wertorientierten Marktverhaltens auf. Solche Werte "
            "zeigen häufig stabilere Kursverläufe und geringere Reaktionsgeschwindigkeit "
            "gegenüber kurzfristigen Marktereignissen."
        ),
        "Zyklisch": (
            "Die Kursentwicklung der Aktie ist im betrachteten Zeitraum deutlich vom "
            "gesamtwirtschaftlichen Umfeld geprägt. Zyklische Werte reagieren häufig stärker "
            "auf Konjunkturveränderungen und makroökonomische Impulse."
        ),
        "Defensiv": (
            "Die Aktie zeigt ein eher defensives Marktverhalten. Solche Werte weisen häufig "
            "eine geringere Schwankungsintensität auf und reagieren weniger stark auf "
            "konjunkturelle Veränderungen."
        ),
        "Volatil": (
            "Die Aktie weist eine erhöhte Schwankungsintensität auf. Kursbewegungen fallen "
            "im betrachteten Zeitraum überdurchschnittlich stark aus, was auf ein sensibles "
            "Reaktionsverhalten gegenüber Marktimpulsen hinweist."
        ),
        "Momentum": (
            "Die Aktie zeigt im betrachteten Zeitraum ein ausgeprägtes Trendverhalten. "
            "Solche Marktphasen sind durch anhaltende Kursbewegungen in eine Richtung "
            "gekennzeichnet, unabhängig von deren Dauer oder Nachhaltigkeit."
        ),
        "Unbekannt": (
            "Das Marktverhalten konnte nicht eindeutig charakterisiert werden. "
            "Die vorliegenden Merkmale sind uneinheitlich oder nicht ausreichend ausgeprägt."
        ),
    }

    ergebnisse = []

    # Eingaben in Listen umwandeln
    profil_liste = [p.strip() for p in profil.split(",")] if profil else []
    trading_liste = [t.strip() for t in trading_status.split(",")] if trading_status else []

    # Marktverhalten (Profil)
    for key in profil_liste:
        ergebnisse.append(texte.get(key, texte["Unbekannt"]))

    # Handelsumfeld (Trading-Status)
    for key in trading_liste:
        ergebnisse.append(texte.get(key, texte["Unbekannt"]))

    if not ergebnisse:
        ergebnisse.append(texte["Unbekannt"])

    # Klarer Hinweis am Ende (UX-Leitplanke)
    ergebnisse.append(
        "Hinweis: Diese Einordnung beschreibt ausschließlich beobachtete Eigenschaften "
        "des Marktverhaltens im betrachteten Zeitraum. Sie stellt keine Bewertung der Aktie "
        "dar und hat keinen Einfluss auf Handelsentscheidungen."
    )

    return "\n\n".join(ergebnisse)

# ------------------------------------------------------
# Indikatoren berechnen
# ------------------------------------------------------
@st.cache_data(show_spinner=False)
def berechne_indikatoren(data: pd.DataFrame) -> pd.DataFrame:
    # Berechne technische Indikatoren hier, z.B.:
    data = data.copy()
    data["MA10"] = data["Close"].rolling(window=10).mean()
    data["MA50"] = data["Close"].rolling(window=50).mean()

    # Sicherstellen, dass High/Low/Close existieren
    for col in ["Open", "High", "Low", "Close"]:
        if col not in data.columns:
            if "Close" in data.columns:
                data[col] = data["Close"]
            else:
                raise ValueError(f"Spalte '{col}' fehlt in den Daten und kann nicht ersetzt werden.")

    close = data["Close"]
    high = data["High"]
    low = data["Low"]

    # ATR (14 Tage)
    high_low = data["High"] - data["Low"]
    high_close = (data["High"] - data["Close"].shift()).abs()
    low_close = (data["Low"] - data["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    data["ATR"] = tr.rolling(window=14).mean()

    # Bollinger Bänder
    ma20 = data["Close"].rolling(window=20).mean()
    std20 = data["Close"].rolling(window=20).std()
    data["BB_Middle"] = ma20
    data["BB_Upper"] = ma20 + 2 * std20
    data["BB_Lower"] = ma20 - 2 * std20

    # MACD Beispiel (schnell/ langsam/ signal)
    exp1 = data["Close"].ewm(span=12, adjust=False).mean()
    exp2 = data["Close"].ewm(span=26, adjust=False).mean()
    data["MACD"] = exp1 - exp2
    data["MACD_Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()
    data["MACD_Hist"] = data["MACD"] - data["MACD_Signal"]

    # RSI (14 Tage)
    delta = data["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    data["RSI"] = 100 - (100 / (1 + rs))

    # Beispiel Support/Resistance - hier Dummywerte (besser mit echter Methode berechnen)
    data["Support1"] = data["Close"].rolling(window=20).min()
    data["Support2"] = data["Close"].rolling(window=50).min()
    data["Resistance1"] = data["Close"].rolling(window=20).max()
    data["Resistance2"] = data["Close"].rolling(window=50).max()

    # Stochastic Oscillator
    stoch = StochasticOscillator(data['High'], data['Low'], data['Close'], window=14, smooth_window=3)
    data['Stoch_%K'] = stoch.stoch()
    data['Stoch_%D'] = stoch.stoch_signal()

    # ADX
    adx_ind = ADXIndicator(data['High'], data['Low'], data['Close'], window=14)
    data['ADX'] = adx_ind.adx()
    data['+DI'] = adx_ind.adx_pos()
    data['-DI'] = adx_ind.adx_neg()

    # Ichimoku Cloud berechnen 
    high_9 = data['High'].rolling(window=9).max()
    low_9 = data['Low'].rolling(window=9).min()
    data['Tenkan_sen'] = (high_9 + low_9) / 2
    
    high_26 = data['High'].rolling(window=26).max()
    low_26 = data['Low'].rolling(window=26).min()
    data['Kijun_sen'] = (high_26 + low_26) / 2
    
    data['Senkou_Span_A'] = ((data['Tenkan_sen'] + data['Kijun_sen']) / 2).shift(26)
    
    high_52 = data['High'].rolling(window=52).max()
    low_52 = data['Low'].rolling(window=52).min()
    data['Senkou_Span_B'] = ((high_52 + low_52) / 2).shift(26)
    
    data['Chikou_Span'] = data['Close'].shift(-26)

    return data
