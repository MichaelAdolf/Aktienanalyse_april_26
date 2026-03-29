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
