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
def lade_daten_aktie(symbol: str, period="3y") -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    data = ticker.history(period=period)
    if data.empty:
        raise ValueError(f"Keine Daten für {symbol} gefunden.")
    return data

# ------------------------------------------------------
# Lade Fundamentaldaten
# ------------------------------------------------------
@st.cache_data(show_spinner=False)
def lade_fundamentaldaten(ticker_symbol):
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

def klassifiziere_aktie(symbol, data, fundamentaldaten):
    ticker = yf.Ticker(symbol)
    info = ticker.info

    sector = info.get("sector")
    industry = info.get("industry")
    marketcap = ticker.fast_info.get("market_cap") or info.get("marketCap")

    kgv = fundamentaldaten.get("kgv")
    div = fundamentaldaten.get("Dividendenrendite (%)")
    umsatz = fundamentaldaten.get("revenue_growth")
    gewinn = fundamentaldaten.get("earnings_growth")

    if "ATR" in data.columns:
        volatilitaet = data["ATR"].iloc[-1] / data["Close"].iloc[-1]
    else:
        volatilitaet = 0.02

    momentum_20 = (data["Close"].iloc[-1] - data["Close"].iloc[-20]) / data["Close"].iloc[-20]

    profil_scores = {
        "Growth": 0,
        "Value": 0,
        "Zyklisch": 0,
        "Defensiv": 0,
    }
    trading_scores = {
        "Volatil": 0,
        "Momentum": 0
    }

    # Growth
    if umsatz and umsatz > 0.10:
        profil_scores["Growth"] += 2
    if gewinn and gewinn > 0.10:
        profil_scores["Growth"] += 2
    if volatilitaet > 0.03:
        profil_scores["Growth"] += 1
    if sector in ["Technology", "Consumer Cyclical"]:
        profil_scores["Growth"] += 1
    if momentum_20 > 0.10:
        profil_scores["Growth"] += 1

    # Value
    if kgv and kgv < 15:
        profil_scores["Value"] += 2
    if div and div > 2:
        profil_scores["Value"] += 1
    if volatilitaet < 0.02:
        profil_scores["Value"] += 1
    if sector in ["Financial Services", "Industrial"]:
        profil_scores["Value"] += 1

    # Zyklisch
    if sector in ["Automobil", "Industrials", "Materials"]:
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

    # Volatil
    if volatilitaet > 0.05:
        trading_scores["Volatil"] += 3
    if marketcap and marketcap < 2e9:
        trading_scores["Volatil"] += 2

    # Momentum
    if momentum_20 > 0.15:
        trading_scores["Momentum"] += 2
    if momentum_20 > 0.25:
        trading_scores["Momentum"] += 2
    if volatilitaet > 0.03:
        trading_scores["Momentum"] += 1

    # Profile filtern und als String zusammenfassen
    max_profil_score = max(profil_scores.values())
    if max_profil_score == 0:
        profil = "Keine"
    else:
        profil = max(profil_scores, key=profil_scores.get)

    # Trading-Status filtern und als String zusammenfassen
    max_trading_score = max(trading_scores.values())
    if max_trading_score == 0:
        trading_status = "Keine"
    else:
        trading_status = max(trading_scores, key=trading_scores.get)

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
    Gibt einen erklärenden Text zu mehreren Profilen und Trading-Status zurück.
    
    Argumente:
    - profil: dict, z.B. {"Growth": True, "Value": False, ...}
    - trading_status: dict, z.B. {"Momentum": True, "Volatil": False}
    
    Rückgabe:
    - String mit erklärenden Texten kombiniert.
    """

    texte = {
        "Growth": (
            "Wachstumsaktien (Growth) zeichnen sich durch ein starkes Umsatz- und "
            "Gewinnwachstum aus. Sie investieren stark in Expansion, besitzen oft hohe "
            "Volatilität und reagieren stark auf Marktstimmung. Typisch sind Tech- oder "
            "Innovationsunternehmen mit überdurchschnittlichem Kursmomentum."
        ),
        "Value": (
            "Value-Aktien sind unterbewertete Unternehmen mit stabilem Geschäftsmodell. "
            "Sie weisen häufig niedrige Bewertungskennzahlen wie das KGV und eine solide "
            "Dividendenrendite auf. Diese Aktien sind defensiver und weniger volatil."
        ),
        "Zyklisch": (
            "Zyklische Aktien hängen stark vom Konjunkturverlauf ab. In Aufschwungphasen "
            "performen sie besonders gut, während sie in Abschwüngen deutliche Verluste "
            "erleiden können. Typisch sind Auto-, Industrie- oder Rohstoffunternehmen."
        ),
        "Defensiv": (
            "Defensive Aktien sind krisenresistent und besitzen stabile Umsätze - unabhängig "
            "vom Konjunkturzyklus. Sie gehören oft zu den Sektoren Gesundheit, "
            "Versorger oder Basiskonsum und haben moderate Volatilität."
        ),
        "Volatil": (
            "Volatile Aktien schwanken stark im Kurs. Sie besitzen hohe ATR-Werte, oft "
            "eine geringe Marktkapitalisierung und reagieren stark auf Nachrichten. "
            "Ideal für Trader, riskanter für langfristige Anleger."
        ),
        "Momentum": (
            "Momentum-Aktien weisen starke und anhaltende Trends auf. Sie steigen oft "
            "überproportional bei positiven Nachrichten und zeigen ein klares technisches "
            "Trendverhalten (RSI, MACD, Breakouts)."
        ),
        "Unbekannt": (
            "Kategorie konnte nicht eindeutig bestimmt werden. Es fehlen Informationen "
            "oder die Aktie erfüllt gemischte Kriterien."
        ),
    }

    ergebnisse = []

    # Falls leerer String übergeben wird, in leere Liste umwandeln
    profil_liste = [p.strip() for p in profil.split(",")] if profil else []
    trading_liste = [t.strip() for t in trading_status.split(",")] if trading_status else []

    # Profiltexte sammeln
    for key in profil_liste:
        if key in texte:
            ergebnisse.append(texte[key])
        else:
            ergebnisse.append(texte["Unbekannt"])

    # Trading-Status-Texte sammeln
    for key in trading_liste:
        if key in texte:
            ergebnisse.append(texte[key])
        else:
            ergebnisse.append(texte["Unbekannt"])

    if not ergebnisse:
        return texte["Unbekannt"]

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
