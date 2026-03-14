import pandas as pd
import yfinance as yf
import numpy as np  # nur wenn du numpy Funktionen brauchst
import plotly.graph_objects as go
import streamlit as st
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, ADXIndicator
from ta.volatility import BollingerBands


from core_magic_3 import (
    lade_aktien,
    lade_daten_aktie,
    lade_analystenbewertung,
    berechne_indikatoren,
    lade_fundamentaldaten,
    klassifiziere_aktie,
    erklaere_kategorien,
    save_watchlist_json
)

class FundamentalAnalysis:
    def fundamental_analyse(self, fundamentaldaten, ticker_symbol):
        sector = fundamentaldaten["sector"]
        kgv = fundamentaldaten["kgv"]
        forward_kgv = fundamentaldaten["forward_kgv"]
        kuv = fundamentaldaten["kuv"]
        kbv = fundamentaldaten["kbv"]
        marge = fundamentaldaten["marge"]
        beta = fundamentaldaten["beta"]
        roe = fundamentaldaten["roe"]
        debt_to_equity = fundamentaldaten["debt_to_equity"]
        revenue_growth = fundamentaldaten["revenue_growth"]
        earnings_growth = fundamentaldaten["earnings_growth"]

        peg = None
        if forward_kgv and earnings_growth and earnings_growth > 0:
            peg = forward_kgv / (earnings_growth * 100)

        sector_thresholds = {
            "Technology":     {"kgv": 30, "kuv": 10, "marge": 0.10, "de_ratio": 150},
            "Financial Services": {"kgv": 15, "kuv": 3, "marge": 0.15, "de_ratio": 300},
            "Industrial":     {"kgv": 20, "kuv": 3, "marge": 0.10, "de_ratio": 200},
            "Healthcare":     {"kgv": 25, "kuv": 6, "marge": 0.10, "de_ratio": 150},
            "Consumer Defensive": {"kgv": 20, "kuv": 4, "marge": 0.08, "de_ratio": 250},
            "Consumer Cyclical": {"kgv": 25, "kuv": 6, "marge": 0.08, "de_ratio": 200},
        }
        sector_config = sector_thresholds.get(sector, {"kgv": 20, "kuv": 4, "marge": 0.10, "de_ratio": 200})

        score = 0
        max_score = 140

        if kgv and kgv < sector_config["kgv"]:
            score += 15
        if forward_kgv and forward_kgv < sector_config["kgv"]:
            score += 10
        if peg and peg < 1.5:
            score += 10
        if kuv and kuv < sector_config["kuv"]:
            score += 15
        if marge and marge > sector_config["marge"]:
            score += 15
        if roe and roe > 0.15:
            score += 15
        if revenue_growth and revenue_growth > 0.07:
            score += 15
        if earnings_growth and earnings_growth > 0.07:
            score += 15
        if debt_to_equity and debt_to_equity < sector_config["de_ratio"]:
            score += 10
        if beta and beta < 1.2:
            score += 10

        ratio = score / max_score
        if ratio >= 0.70:
            ampel = "🟢"
        elif ratio >= 0.45:
            ampel = "🟡"
        else:
            ampel = "🔴"

        return {
            "Aktie": ticker_symbol,
            "Sektor": sector,
            "KGV": kgv,
            "Forward KGV": forward_kgv,
            "KUV": kuv,
            "KBV": kbv,
            "Marge (%)": f"{marge*100:.1f}%" if marge else "n/a",
            "ROE (%)": f"{roe*100:.1f}%" if roe else "n/a",
            "PEG Ratio": peg,
            "Beta": beta,
            "Umsatzwachstum": revenue_growth,
            "Gewinnwachstum": earnings_growth,
            "Debt/Equity": debt_to_equity,
            "Score": score,
            "Ampel": ampel
        }
    
    # ------------------------------------------------------------
    # Fundamentaldaten: Score Interpretation
    # ------------------------------------------------------------
    def fundamental_interpretation(self, result):
        aktie = result["Aktie"]
        ampel = result["Ampel"]

        kgv = result["KGV"]
        kuv = result["KUV"]
        kbv = result["KBV"]
        marge = result["Marge (%)"]
        beta = result["Beta"]
        score = result["Score"]

        st.subheader(f"Fundamentale Einschätzung:")

        # Ampel-Interpretation
        if ampel == "🟢":
            st.markdown(
                f"""
                **{ampel} Sehr solide Fundamentaldaten (Score: {score}/100)**  
                Die Aktie zeigt in mehreren zentralen Bereichen überzeugende Werte.  
                Dies spricht für eine **attraktive Bewertung** und ein **günstiges Risiko-Rendite-Verhältnis**.
                """
            )
        elif ampel == "🟡":
            st.markdown(
                f"""
                **{ampel} Neutrale Fundamentaldaten (Score: {score}/100)**  
                Die Kennzahlen sind gemischt. Einige Bereiche schneiden gut ab, andere schwächer.  
                Eine **Beobachtung** oder **Einstieg bei besserer Bewertung** kann sinnvoll sein.
                """
            )
        else:
            st.markdown(
                f"""
                **{ampel} Schwache Fundamentaldaten (Score: {score}/100)**  
                Die Aktie weist mehrere kritische Bewertungs- oder Risikofaktoren auf.  
                Eine Investition sollte nur nach tieferer Analyse erwogen werden.
                """
            )

        # Detailanalyse
        st.markdown("### Detailanalyse der Kennzahlen")

        def bullet(text, value):
            return f"- **{text}:** {value}"

        st.markdown(
            "\n".join([
                bullet("KGV (Bewertung Gewinn)", kgv),
                bullet("KUV (Bewertung Umsatz)", kuv),
                bullet("KBV (Bewertung Substanz)", kbv),
                bullet("Gewinnmarge", marge),
                bullet("Beta (Risiko/Volatilität)", beta),
            ])
        )

        # Einordnung der Kennzahlen
        st.markdown("### Kurzinterpretation der Faktoren")

        interpretation = []

        # KGV
        try:
            kgv_val = float(kgv)
            if kgv_val < 15:
                interpretation.append("• **KGV niedrig:** Die Aktie ist im Vergleich zum Gewinn günstig bewertet.")
            elif kgv_val > 35:
                interpretation.append("• **KGV sehr hoch:** Markt erwartet starkes Wachstum – oder Aktie ist überbewertet.")
            else:
                interpretation.append("• **KGV neutral:** Bewertung im marktüblichen Bereich.")
        except:
            pass

        # KUV
        try:
            kuv_val = float(kuv)
            if kuv_val < 3:
                interpretation.append("• **KUV attraktiv:** Umsatzbewertung spricht für solide Bewertung.")
            else:
                interpretation.append("• **KUV erhöht:** Markt zahlt Aufpreis für Wachstum oder Marke.")
        except:
            pass

        # Marge
        try:
            marge_val = float(marge.replace("%",""))
            if marge_val > 15:
                interpretation.append("• **Hohe Marge:** Starkes, profitables Geschäftsmodell.")
            else:
                interpretation.append("• **Niedrige Marge:** Wettbewerb hoch oder Geschäftsmodell wenig profitabel.")
        except:
            pass

        # Beta
        try:
            beta_val = float(beta)
            if beta_val < 1:
                interpretation.append("• **Niedriges Beta:** Aktie schwankt weniger als der Markt (geringeres Risiko).")
            else:
                interpretation.append("• **Hohes Beta:** Überdurchschnittliche Schwankung → höheres Risiko.")
        except:
            pass

        st.markdown("\n".join(interpretation))

    # ------------------------------------------------------------
    # Fundamentaldaten: Summary
    # ------------------------------------------------------------
    def fundamental_summary(self, result):
        ampel = result["Ampel"]
        score = result["Score"]

        # Ampel-Interpretation
        if ampel == "🟢":
            st.markdown(
                f"""
                **{ampel} Sehr solide Fundamentaldaten (Score: {score}/100)**  
                Die Aktie zeigt in mehreren zentralen Bereichen überzeugende Werte.  
                Dies spricht für eine **attraktive Bewertung** und ein **günstiges Risiko-Rendite-Verhältnis**.
                """
            )
        elif ampel == "🟡":
            st.markdown(
                f"""
                **{ampel} Neutrale Fundamentaldaten (Score: {score}/100)**  
                Die Kennzahlen sind gemischt. Einige Bereiche schneiden gut ab, andere schwächer.  
                Eine **Beobachtung** oder **Einstieg bei besserer Bewertung** kann sinnvoll sein.
                """
            )
        else:
            st.markdown(
                f"""
                **{ampel} Schwache Fundamentaldaten (Score: {score}/100)**  
                Die Aktie weist mehrere kritische Bewertungs- oder Risikofaktoren auf.  
                Eine Investition sollte nur nach tieferer Analyse erwogen werden.
                """
            )

class Analystenbewertung:
    def zeige_analystenbewertung(symbol):
        data = lade_analystenbewertung(symbol)

        st.markdown("<div class='kachel'>", unsafe_allow_html=True)
        st.markdown("### 🧠 Analystenbewertungen")

        # 🟦 Zusammenfassung (Buy/Hold/Sell)
        if data["summary"] is not None:
            st.markdown("#### 📊 Rating-Übersicht")
            st.table(data["summary"])
        else:
            st.info("Keine Rating-Übersicht verfügbar.")

        # 🟪 Historische Empfehlungen (Buy/Hold/Sell)
        if data["recommendations"] is not None:
            st.markdown("#### 🕒 Historische Empfehlungen")
            st.dataframe(data["recommendations"].tail(20))
        else:
            st.info("Keine historischen Empfehlungen verfügbar.")

        # 🟧 EPS & Wachstumsprognosen
        if data["analysis"] is not None:
            st.markdown("#### 📈 Analysten-Prognosen (EPS, Revenue, Growth)")
            st.dataframe(data["analysis"])
        else:
            st.info("Keine detaillierten Analystenanalysen verfügbar.")

        st.markdown("</div>", unsafe_allow_html=True)

    def berechne_rating_bar(self, summary_df):
        # Falls dict → zu DataFrame konvertieren
        if isinstance(summary_df, dict):
            summary_df = pd.DataFrame([summary_df])

        # Falls summary_df None ist → sicher abfangen
        if summary_df is None:
            return {"Buy": 0, "Hold": 0, "Sell": 0}

        # Falls DataFrame leer ist → sicher abfangen
        if summary_df.empty:
            return {"Buy": 0, "Hold": 0, "Sell": 0}

        # typischerweise: "strongBuy", "buy", "hold", "sell", "strongSell"
        row = summary_df.iloc[0]

        return {
            "Buy": row.get("buy", 0) + row.get("strongBuy", 0),
            "Hold": row.get("hold", 0),
            "Sell": row.get("sell", 0) + row.get("strongSell", 0),
        }

    def zeichne_rating_gauge(self, rating_counts):
        total = sum(rating_counts.values())
        if total == 0:
            buy_percent = 0
        else:
            buy_percent = rating_counts.get("Buy", 0) / total * 100

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=buy_percent,
            title={'text': "Buy-Empfehlungen in %"},
            delta={'increasing': {'color': "green"}, 'decreasing': {'color': "red"}},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': "green"},
                'steps': [
                    {'range': [0, 33], 'color': "red"},
                    {'range': [33, 66], 'color': "orange"},
                    {'range': [66, 100], 'color': "green"}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': buy_percent
                }
            }
        ))
        fig.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

class IndikatorAnalyses:    
    def bollinger_signal_2(data: pd.DataFrame) -> str:
        """
        Bollinger-Band-Signal mit Toleranz und Rebound-Logik.

        Logik:
        - 🟢 Kaufsignal, wenn der Schlusskurs maximal 1,5 % über dem unteren Band liegt 
        ODER vorher unter dem Band lag und jetzt darüber schließt (Rebound).
        - 🔴 Verkaufssignal, wenn der Schlusskurs maximal 1,5 % unter dem oberen Band liegt 
        ODER vorher über dem Band lag und jetzt darunter schließt (Rebound).
        - 🟡 Andernfalls Haltesignal.

        Erwartet Spalten: 'Close', 'BB_Upper', 'BB_Lower'
        """
        if len(data) < 2:
            return "🟡 Zu wenige Daten für Bollinger-Signal"

        if not {"Close", "BB_Upper", "BB_Lower"}.issubset(data.columns):
            return "Keine Bollinger-Band-Daten vorhanden"

        if len(data) < 2:
            return "Zu wenige Daten für Signal"

        letzte = data.iloc[-1]
        vorletzte = data.iloc[-2]

        close = letzte["Close"]
        upper = letzte["BB_Upper"]
        lower = letzte["BB_Lower"]

        if pd.isna(upper) or pd.isna(lower):
            return "Keine gültigen Bollinger-Daten"

        # Distanz zum oberen und unteren Band in Prozent
        dist_lower = (close - lower) / lower
        dist_upper = (upper - close) / upper

        # --- Kaufsignal: Nähe zum unteren Band oder Rebound
        if (dist_lower <= 0.015) or (
            vorletzte["Close"] < vorletzte["BB_Lower"] and close > lower
        ):
            return {"signal": 1, "label": "Kurs im definierten bereich um das untere Bollinger Band"}

        # --- Verkaufssignal: Nähe zum oberen Band oder Rebound
        elif (dist_upper <= 0.015) or (
            vorletzte["Close"] > vorletzte["BB_Upper"] and close < upper
        ):
            return {"signal": -1, "label": "Kurs im definierten bereich um das obere Bollinger Band"}

        # --- Haltesignal
        else:
            return {"signal": 0, "label": "Kurs in keinem Kriterium sondern zwischen dem oberen und unteren Billinger Band"}

    def rsi_signal_2(data):
        """
        Einfaches Swingtrading-Signal basierend auf RSI und MA10.
        Rückgabe: String mit Signal und Emoji.
        """
        letzte = data.iloc[-1]
        if letzte["RSI"] < 35:
            return {"signal": 1, "label": "Oversold"}
        elif letzte["RSI"] > 60:
            return {"signal": -1, "label": "Overbought"}
        else:
            return {"signal": 0, "label": "Neutral"}

    def macd_signal_2(data):
        """
        Verbesserte MACD-Logik:
        - Erkennung von MACD/Signal-Kreuzungen
        - Einbau von Momentum- und Trendfiltern
        - Sanfter: verhindert Fehlsignale in Seitwärtsmärkten
        """

        if len(data) < 3:
            return "🟡 Zu wenige Daten für MACD-Signal"

        # Zeilen
        letzte = data.iloc[-1]
        vorletzte = data.iloc[-2]
        dritte = data.iloc[-3]

        macd = letzte["MACD"]
        signal = letzte["MACD_Signal"]

        # --- 1️⃣ Grundlegende Kreuzungen ---
        bullish_cross = vorletzte["MACD"] < vorletzte["MACD_Signal"] and macd > signal
        bearish_cross = vorletzte["MACD"] > vorletzte["MACD_Signal"] and macd < signal

        # --- 2️⃣ Momentum-Filter ---
        # Verhindert Signale ohne Kraft
        momentum_positive = (letzte["MACD"] - vorletzte["MACD"]) > 0
        momentum_negative = (letzte["MACD"] - vorletzte["MACD"]) < 0

        # --- 3️⃣ Trendfilter (MACD muss mind. leicht getrennt sein) ---
        distance = abs(macd - signal)
        min_dist = 0.1  # Tuning möglich

        # --- 4️⃣ Entscheidung ---
        # Kaufsignal: Kreuzung + Momentum + minimale Distanz
        if bullish_cross and momentum_positive and distance > min_dist:
            return {"signal": 1, "label": "Starkes Kaufsignal (Cross + Momentum)"}

        # Verkauf: Kreuzung + Momentum + Distanz
        elif bearish_cross and momentum_negative and distance > min_dist:
            return {"signal": -1, "label": "Starkes Verkaufssignal (Cross + Momentum)"}

        # Schwaches Kaufsignal (Cross aber wenig Momentum)
        elif bullish_cross:
            return {"signal": 0, "label": "Schwaches Kaufsignal (Cross ohne Momentum)"}

        # Schwaches Verkaufssignal
        elif bearish_cross:
            return {"signal": 0, "label": "Schwaches Verkaufsignal (Cross ohne Momentum)"}

        else:
            return {"signal": 0, "label": "Haltesignal"}
    
    def adx_signal_2(data, adx_threshold=25):
        """
        ADX-basierte Signale:
        - Trendstärke über Schwelle = Signal
        - Directional Indicator +DI und -DI für Richtung
        """
        letzte = data.iloc[-1]

        if letzte["ADX"] < adx_threshold:
            return {"signal": 0, "label": "Kein klarer Trend (ADX zu niedrig)"}
        if letzte["+DI"] > letzte["-DI"]:
            return {"signal": 1, "label": "Aufwärtstrend (ADX stark, +DI > -DI)"}
        else:
            return {"signal": -1, "label": "Abwärtstrend (ADX stark, +DI < -DI)"}
   
    def stochastic_signal_2(data: pd.DataFrame) -> str:
        """
        Generiert Kaufs- oder Verkaufssignal basierend auf Stochastic Oscillator.

        Erwartet, dass die Spalten 'Stoch_%K' und 'Stoch_%D' im DataFrame vorhanden sind.
        """

        if len(data) < 2:
            return "🟡 Zu wenige Daten für Stochastic-Signal"

        if not {"Stoch_%K", "Stoch_%D"}.issubset(data.columns):
            return "Daten für Stochastic Oscillator fehlen"

        letzte = data.iloc[-1]
        vorletzte = data.iloc[-2]

        # Kaufsignal: %K kreuzt %D von unten nach oben und beide unter 20
        if (vorletzte["Stoch_%K"] < vorletzte["Stoch_%D"]) and (letzte["Stoch_%K"] > letzte["Stoch_%D"]) and (letzte["Stoch_%K"] < 20) and (letzte["Stoch_%D"] < 20):
            return {"signal": 1, "label": "Kaufsignal"}

        # Verkaufssignal: %K kreuzt %D von oben nach unten und beide über 80
        elif (vorletzte["Stoch_%K"] > vorletzte["Stoch_%D"]) and (letzte["Stoch_%K"] < letzte["Stoch_%D"]) and (letzte["Stoch_%K"] > 80) and (letzte["Stoch_%D"] > 80):
            return {"signal": -1, "label": "Verkaufsignal"}

        else:
            return {"signal": 0, "label": "Haltesignal"}
        
    def bollinger_signal_3(data: pd.DataFrame) -> str:
        """
        Bollinger-Band-Signal mit Toleranz und Rebound-Logik.

        Logik:
        - 🟢 Kaufsignal, wenn der Schlusskurs maximal 1,5 % über dem unteren Band liegt 
        ODER vorher unter dem Band lag und jetzt darüber schließt (Rebound).
        - 🔴 Verkaufssignal, wenn der Schlusskurs maximal 1,5 % unter dem oberen Band liegt 
        ODER vorher über dem Band lag und jetzt darunter schließt (Rebound).
        - 🟡 Andernfalls Haltesignal.

        Erwartet Spalten: 'Close', 'BB_Upper', 'BB_Lower'
        """
        if len(data) < 2:
            return "🟡 Zu wenige Daten für Bollinger-Signal"

        if not {"Close", "BB_Upper", "BB_Lower"}.issubset(data.columns):
            return "Keine Bollinger-Band-Daten vorhanden"

        if len(data) < 2:
            return "Zu wenige Daten für Signal"

        letzte = data.iloc[-1]
        vorletzte = data.iloc[-2]

        close = letzte["Close"]
        upper = letzte["BB_Upper"]
        lower = letzte["BB_Lower"]

        if pd.isna(upper) or pd.isna(lower):
            return "Keine gültigen Bollinger-Daten"

        # Distanz zum oberen und unteren Band in Prozent
        dist_lower = (close - lower) / lower
        dist_upper = (upper - close) / upper

        # --- Kaufsignal: Nähe zum unteren Band oder Rebound
        if (dist_lower <= 0.015) or (
            vorletzte["Close"] < vorletzte["BB_Lower"] and close > lower
        ):
            return {"signal": 1, "label": "Kurs im definierten bereich um das untere Bollinger Band"}

        # --- Verkaufssignal: Nähe zum oberen Band oder Rebound
        elif (dist_upper <= 0.015) or (
            vorletzte["Close"] > vorletzte["BB_Upper"] and close < upper
        ):
            return {"signal": -1, "label": "Kurs im definierten bereich um das obere Bollinger Band"}

        # --- Haltesignal
        else:
            return {"signal": 0, "label": "Kurs in keinem Kriterium sondern zwischen dem oberen und unteren Billinger Band"}

    def rsi_signal_3(data):
        """
        Einfaches Swingtrading-Signal basierend auf RSI und MA10.
        Rückgabe: String mit Signal und Emoji.
        """
        letzte = data.iloc[-1]
        if letzte["RSI"] < 35:
            return {"signal": 1, "label": "Oversold"}
        elif letzte["RSI"] > 60:
            return {"signal": -1, "label": "Overbought"}
        else:
            return {"signal": 0, "label": "Neutral"}

    def macd_signal_3(data):
        """
        Verbesserte MACD-Logik:
        - Erkennung von MACD/Signal-Kreuzungen
        - Einbau von Momentum- und Trendfiltern
        - Sanfter: verhindert Fehlsignale in Seitwärtsmärkten
        """

        if len(data) < 3:
            return "🟡 Zu wenige Daten für MACD-Signal"

        # Zeilen
        letzte = data.iloc[-1]
        vorletzte = data.iloc[-2]
        dritte = data.iloc[-3]

        macd = letzte["MACD"]
        signal = letzte["MACD_Signal"]

        # --- 1️⃣ Grundlegende Kreuzungen ---
        bullish_cross = vorletzte["MACD"] < vorletzte["MACD_Signal"] and macd > signal
        bearish_cross = vorletzte["MACD"] > vorletzte["MACD_Signal"] and macd < signal

        # --- 2️⃣ Momentum-Filter ---
        # Verhindert Signale ohne Kraft
        momentum_positive = (letzte["MACD"] - vorletzte["MACD"]) > 0
        momentum_negative = (letzte["MACD"] - vorletzte["MACD"]) < 0

        # --- 3️⃣ Trendfilter (MACD muss mind. leicht getrennt sein) ---
        distance = abs(macd - signal)
        min_dist = 0.1  # Tuning möglich

        # --- 4️⃣ Entscheidung ---
        # Kaufsignal: Kreuzung + Momentum + minimale Distanz
        if bullish_cross and momentum_positive and distance > min_dist:
            return {"signal": 1, "label": "Starkes Kaufsignal (Cross + Momentum)"}

        # Verkauf: Kreuzung + Momentum + Distanz
        elif bearish_cross and momentum_negative and distance > min_dist:
            return {"signal": -1, "label": "Starkes Verkaufssignal (Cross + Momentum)"}

        # Schwaches Kaufsignal (Cross aber wenig Momentum)
        elif bullish_cross:
            return {"signal": 0, "label": "Schwaches Kaufsignal (Cross ohne Momentum)"}

        # Schwaches Verkaufssignal
        elif bearish_cross:
            return {"signal": 0, "label": "Schwaches Verkaufsignal (Cross ohne Momentum)"}

        else:
            return {"signal": 0, "label": "Haltesignal"}
    
    def adx_signal_3(data, adx_threshold=25):
        """
        ADX-basierte Signale:
        - Trendstärke über Schwelle = Signal
        - Directional Indicator +DI und -DI für Richtung
        """
        letzte = data.iloc[-1]

        if letzte["ADX"] < adx_threshold:
            return {"signal": 0, "label": "Kein klarer Trend (ADX zu niedrig)"}
        if letzte["+DI"] > letzte["-DI"]:
            return {"signal": 1, "label": "Aufwärtstrend (ADX stark, +DI > -DI)"}
        else:
            return {"signal": -1, "label": "Abwärtstrend (ADX stark, +DI < -DI)"}
   
    def stochastic_signal_3(data: pd.DataFrame) -> str:
        """
        Generiert Kaufs- oder Verkaufssignal basierend auf Stochastic Oscillator.

        Erwartet, dass die Spalten 'Stoch_%K' und 'Stoch_%D' im DataFrame vorhanden sind.
        """

        if len(data) < 2:
            return "🟡 Zu wenige Daten für Stochastic-Signal"

        if not {"Stoch_%K", "Stoch_%D"}.issubset(data.columns):
            return "Daten für Stochastic Oscillator fehlen"

        letzte = data.iloc[-1]
        vorletzte = data.iloc[-2]

        # Kaufsignal: %K kreuzt %D von unten nach oben und beide unter 20
        if (vorletzte["Stoch_%K"] < vorletzte["Stoch_%D"]) and (letzte["Stoch_%K"] > letzte["Stoch_%D"]) and (letzte["Stoch_%K"] < 20) and (letzte["Stoch_%D"] < 20):
            return {"signal": 1, "label": "Kaufsignal"}

        # Verkaufssignal: %K kreuzt %D von oben nach unten und beide über 80
        elif (vorletzte["Stoch_%K"] > vorletzte["Stoch_%D"]) and (letzte["Stoch_%K"] < letzte["Stoch_%D"]) and (letzte["Stoch_%K"] > 80) and (letzte["Stoch_%D"] > 80):
            return {"signal": -1, "label": "Verkaufsignal"}

        else:
            return {"signal": 0, "label": "Haltesignal"}

class Gewichtung:
    KATEGORIE_STRATEGIEN = {
        "Growth": {
            "signale": ["MACD", "ADX", "Bollinger"],
            "weights": {"MACD": 0.2, "ADX": 0.6, "Bollinger": 0.2}
        },
        "Value": {
            "signale": ["RSI", "Stochastic", "Bollinger"],
            "weights": {"RSI": 0.5, "Stochastic": 0.3, "Bollinger": 0.2}
        },
        "Zyklisch": {
            "signale": ["MACD", "ADX"],
            "weights": {"MACD": 0.6, "ADX": 0.4}
        },
        "Defensiv": {
            "signale": ["ADX", "Bollinger"],
            "weights": {"ADX": 0.9, "Bollinger": 0.1}
        },
        "Volatil": {
            "signale": ["Bollinger", "Stochastic"],
            "weights": {"Bollinger": 0.5, "Stochastic": 0.5}
        },
        "Momentum": {
            "signale": ["MACD", "RSI", "ADX"],
            "weights": {"MACD": 0.5, "RSI": 0.3, "ADX": 0.2}
        }
    }

    TRADING_STATUS_MODIFIKATOR = {
        "Momentum": {
            "Trend_Signale": 1.2,   # erhöhe Gewicht für Trend-Indikatoren
            "Volatilitaet_Signale": 0.8
        },
        "Volatil": {
            "Trend_Signale": 0.8,
            "Volatilitaet_Signale": 1.2
        },
        "Keine": {
            "Trend_Signale": 1.0,
            "Volatilitaet_Signale": 1.0
        }
    }

class SwingTrading:
    def kombiniertes_signal_2(data: pd.DataFrame, kategorie: str, trading_status: str = "Keine"):
        strategie = Gewichtung.KATEGORIE_STRATEGIEN[kategorie]
        modifikator = Gewichtung.TRADING_STATUS_MODIFIKATOR.get(trading_status, Gewichtung.TRADING_STATUS_MODIFIKATOR[trading_status])

        signal_funktionen = {
            "RSI": IndikatorAnalyses.rsi_signal_2,
            "MACD": IndikatorAnalyses.macd_signal_2,
            "ADX": IndikatorAnalyses.adx_signal_2,
            "Bollinger": IndikatorAnalyses.bollinger_signal_2,
            "Stochastic": IndikatorAnalyses.stochastic_signal_2
        }

        SIGNAL_TYPEN = {
        "RSI": "Volatilitaet_Signale",
        "MACD": "Trend_Signale",
        "ADX": "Trend_Signale",
        "Bollinger": "Volatilitaet_Signale",
        "Stochastic": "Volatilitaet_Signale"
    }

        gesamt_score = 0
        details = {}

        for name in strategie["signale"]:
            # Signal holen
            result = signal_funktionen[name](data)
            basisgewicht = strategie["weights"][name]

            # Signaltyp bestimmen
            signal_typ = SIGNAL_TYPEN.get(name, None)
            faktor = modifikator.get(signal_typ, 1.0)

            # Effektives Gewicht
            effektives_gewicht = basisgewicht * faktor

            # Score
            gesamt_score += result["signal"] * effektives_gewicht

            # Debug / Anzeige
            details[name] = {
                "Signal": result["signal"],
                "Label": result["label"],
                "Basisgewicht": basisgewicht,
                "Typ": signal_typ,
                "Status_Faktor": faktor,
                "Effektives_Gewicht": round(effektives_gewicht, 3)
            }

        # Finale Entscheidung
        if gesamt_score > 0.25:
            entscheidung = "🟢 Kaufen"
        elif gesamt_score < -0.25:
            entscheidung = "🔴 Verkaufen"
        else:
            entscheidung = "🟡 Halten"

        return entscheidung, details, round(gesamt_score, 3)
    
    def kombiniertes_signal_3(data: pd.DataFrame, kategorie: str, trading_status: str = "Keine"):
        strategie = Gewichtung.KATEGORIE_STRATEGIEN[kategorie]
        modifikator = Gewichtung.TRADING_STATUS_MODIFIKATOR.get(trading_status, Gewichtung.TRADING_STATUS_MODIFIKATOR[trading_status])

        signal_funktionen = {
            "RSI": IndikatorAnalyses.rsi_signal_3,
            "MACD": IndikatorAnalyses.macd_signal_3,
            "ADX": IndikatorAnalyses.adx_signal_3,
            "Bollinger": IndikatorAnalyses.bollinger_signal_3,
            "Stochastic": IndikatorAnalyses.stochastic_signal_3
        }

        SIGNAL_TYPEN = {
        "RSI": "Volatilitaet_Signale",
        "MACD": "Trend_Signale",
        "ADX": "Trend_Signale",
        "Bollinger": "Volatilitaet_Signale",
        "Stochastic": "Volatilitaet_Signale"
    }

        gesamt_score = 0
        details = {}

        for name in strategie["signale"]:
            # Signal holen
            result = signal_funktionen[name](data)
            basisgewicht = strategie["weights"][name]

            # Signaltyp bestimmen
            signal_typ = SIGNAL_TYPEN.get(name, None)
            faktor = modifikator.get(signal_typ, 1.0)

            # Effektives Gewicht
            effektives_gewicht = basisgewicht * faktor

            # Score
            gesamt_score += result["signal"] * effektives_gewicht

            # Debug / Anzeige
            details[name] = {
                "Signal": result["signal"],
                "Label": result["label"],
                "Basisgewicht": basisgewicht,
                "Typ": signal_typ,
                "Status_Faktor": faktor,
                "Effektives_Gewicht": round(effektives_gewicht, 3)
            }

        # Finale Entscheidung
        if gesamt_score > 0.25:
            entscheidung = "🟢 Kaufen"
        elif gesamt_score < -0.25:
            entscheidung = "🔴 Verkaufen"
        else:
            entscheidung = "🟡 Halten"

        return entscheidung, details, round(gesamt_score, 3)
    
    def zeige_technische_signale_2(self, data, KATEGORIE_STRATEGIEN, TRADING_STATUS_MODIFIKATOR):
        # Übersichtstabelle der Einzel-Signale
        df_signale = pd.DataFrame({
            "Bollinger": [IndikatorAnalyses.bollinger_signal_2(data)],
            "RSI": [IndikatorAnalyses.rsi_signal_2(data)],
            "MACD": [IndikatorAnalyses.macd_signal_2(data)],
            "ADX": [IndikatorAnalyses.adx_signal_2(data)],
            "Stochastic": [IndikatorAnalyses.stochastic_signal_2(data)]
        })

        #st.table(df_signale)

        # Kombiniertes Signal berechnen
        gesamt_signal, alle_signale, gesamtscore = SwingTrading.kombiniertes_signal_2(data, KATEGORIE_STRATEGIEN, TRADING_STATUS_MODIFIKATOR)

        st.markdown("---")
        st.subheader("🧩 Kombiniertes Handelssignal_2")
        st.write(gesamt_signal)

        # Detailansicht
        with st.expander("Details zu den Einzelsignalen"):
            st.write(gesamtscore)
            for name, sig in alle_signale.items():
                st.write(f"**{name}**: {sig}")
    
    def zeige_swingtrading_signal(self, data, kategorie, TradingStatus):
        # Kombiniertes Signal berechnen
        gesamt_signal, alle_signale, geasmtscore = SwingTrading.kombiniertes_signal_2(data, kategorie, TradingStatus)

        st.write(gesamt_signal)

    def zeige_swingtrading_signal(self, data, kategorie, TradingStatus):
        # Kombiniertes Signal berechnen
        gesamt_signal, alle_signale, geasmtscore = SwingTrading.kombiniertes_signal_2(data, kategorie, TradingStatus)

        st.write(gesamt_signal)

    def zeige_swingtrading_signalauswertung(self, data, Auswertung_tage, min_veraenderung,  Kategorie, TradingStatus,):
        """
        Führt die Analyse der Kaufsignal-Perioden durch
        und zeigt nur die prozentzele trefferquote in Streamlit an.
        """

        # Analyse aus Kernfunktion laden
        analyse_ergebnis = PeriodAnalysis.analyse_kaufsignal_perioden(data, Auswertung_tage, min_veraenderung, Kategorie, TradingStatus,)
        st.write(f"Anzahl Kaufsignale (gesamt): {analyse_ergebnis.get('Anzahl_Kaufsignale', 0)}")

        # Perioden-Bewertung prüfen
        if "Perioden_Bewertung" not in analyse_ergebnis:
            st.info("Keine Perioden-Bewertung verfügbar.")
            return

        df_details = pd.DataFrame(analyse_ergebnis["Perioden_Bewertung"])
        df_details.columns = ["Start", "Ende", "Signal", "Wert1", "Wert2", "Beschreibung", "ExtraInfo"]

        # Signal in Bool umwandeln
        df_details["Signal"] = df_details["Signal"].astype(str).str.upper() == "TRUE"

        # Start-Datum als datetime
        df_details["Start"] = pd.to_datetime(df_details["Start"])

        # Ende-Datum als datetime
        df_details["Ende"] = pd.to_datetime(df_details["Ende"])

        # letztes Kursdatum
        letztes_datum = data.index[-1]

        # Ende + Bewertungsdauer = Zeitpunkt, ab dem man die Periode werten darf
        df_details["Bewertung_fertig_ab"] = df_details["Ende"] + pd.Timedelta(days=Auswertung_tage)

        # Perioden klassifizieren
        df_abgeschlossen = df_details[df_details["Bewertung_fertig_ab"] <= letztes_datum]
        df_offen = df_details[df_details["Bewertung_fertig_ab"] > letztes_datum]

        # Neue korrekte Trefferquote berechnen
        gesamt = len(df_abgeschlossen)
        if gesamt > 0:
            prozent_true = (df_abgeschlossen["Signal"].sum() / gesamt) * 100
        else:
            prozent_true = 0

        st.write(f"Ausgewertete abgeschlossene Perioden: {gesamt}")
        st.metric("Trefferquote (nur abgeschlossene Perioden)", f"{prozent_true:.2f} %")
        
        with st.expander("Details zu den Perioden"):
            st.markdown("### 📘 Abgeschlossene Signalperioden")
            if len(df_abgeschlossen) > 0:
                st.dataframe(df_abgeschlossen)
            else:
                st.info("Es gibt aktuell keine abgeschlossenen Perioden.")

            st.markdown("### ⏳ Laufende Signalperioden")
            if len(df_offen) > 0:
                df_tmp = df_offen.copy()
                df_tmp["Tage_bis_fertig"] = (df_tmp["Bewertung_fertig_ab"] - letztes_datum).dt.days
                st.dataframe(df_tmp)
            else:
                st.success("Alle abgeschlossenen Perioden wurden ausgewertet – keine offenen Perioden vorhanden.")

    def zeige_swingtrading_signalauswertung_2(self, data, Auswertung_tage, min_veraenderung,  Kategorie, TradingStatus,):
        """
        Führt die Analyse der Kaufsignal-Perioden durch
        und zeigt nur die prozentzele trefferquote in Streamlit an.
        """

        # Analyse aus Kernfunktion laden
        analyse_ergebnis = PeriodAnalysis.analyse_kaufsignal_perioden_2(data, Auswertung_tage, min_veraenderung, Kategorie, TradingStatus,)
        st.write(f"Anzahl Kaufsignale (gesamt): {analyse_ergebnis.get('Anzahl_Kaufsignale', 0)}")

        # Perioden-Bewertung prüfen
        if "Perioden_Bewertung" not in analyse_ergebnis:
            st.info("Keine Perioden-Bewertung verfügbar.")
            return

        df_details = pd.DataFrame(analyse_ergebnis["Perioden_Bewertung"])
        df_details.columns = ["Start", "Ende", "Signal", "Wert1", "Wert2", "Beschreibung", "ExtraInfo"]

        # Signal in Bool umwandeln
        df_details["Signal"] = df_details["Signal"].astype(str).str.upper() == "TRUE"

        # Start-Datum als datetime
        df_details["Start"] = pd.to_datetime(df_details["Start"])

        # Ende-Datum als datetime
        df_details["Ende"] = pd.to_datetime(df_details["Ende"])

        # letztes Kursdatum
        letztes_datum = data.index[-1]

        # Ende + Bewertungsdauer = Zeitpunkt, ab dem man die Periode werten darf
        df_details["Bewertung_fertig_ab"] = df_details["Ende"] + pd.Timedelta(days=Auswertung_tage)

        # Perioden klassifizieren
        df_abgeschlossen = df_details[df_details["Bewertung_fertig_ab"] <= letztes_datum]
        df_offen = df_details[df_details["Bewertung_fertig_ab"] > letztes_datum]

        # Neue korrekte Trefferquote berechnen
        gesamt = len(df_abgeschlossen)
        if gesamt > 0:
            prozent_true = (df_abgeschlossen["Signal"].sum() / gesamt) * 100
        else:
            prozent_true = 0

        st.write(f"Ausgewertete abgeschlossene Perioden: {gesamt}")
        st.metric("Trefferquote (nur abgeschlossene Perioden)", f"{prozent_true:.2f} %")
        
        with st.expander("Details zu den Perioden"):
            st.markdown("### 📘 Abgeschlossene Signalperioden")
            if len(df_abgeschlossen) > 0:
                st.dataframe(df_abgeschlossen)
            else:
                st.info("Es gibt aktuell keine abgeschlossenen Perioden.")

            st.markdown("### ⏳ Laufende Signalperioden")
            if len(df_offen) > 0:
                df_tmp = df_offen.copy()
                df_tmp["Tage_bis_fertig"] = (df_tmp["Bewertung_fertig_ab"] - letztes_datum).dt.days
                st.dataframe(df_tmp)
            else:
                st.success("Alle abgeschlossenen Perioden wurden ausgewertet – keine offenen Perioden vorhanden.")

class PeriodAnalysis:
    @staticmethod
    def analyse_kaufsignal_perioden(full_data: pd.DataFrame,
                                Auswertung_tage,
                                min_veraenderung,
                                Kategorie, TradingStatus,
                                min_len_window: int = 20,
                                innerhalb_zeitraum: bool = True):
        # 1. Alle Signale über den gesamten Zeitraum generieren
        signale_liste = []

        for i in range(min_len_window, len(full_data)):
            fenster = full_data.iloc[:i+1]
            entscheidung, einzelsignale, gesamtscore = SwingTrading.kombiniertes_signal_2(fenster, Kategorie, TradingStatus)  # Deine Signalgenerierung
            datum = fenster.index[-1]
            signale_liste.append({"Datum": datum, "Entscheidung": entscheidung, **einzelsignale})

        signale_df = pd.DataFrame(signale_liste)  # signale_df hier erzeugen!

        # 2. Nur Kaufsignale herausfiltern
        kaufsignale_df = signale_df[signale_df["Entscheidung"].str.contains("Kauf")].copy()

        if kaufsignale_df.empty:
            return {
                "Anzahl_Kaufsignale": 0,
                "Trefferquote_Kauf (%)": None,
                "Gesamt_Signale": 0,
                "Signal_Details": signale_df,
                "Perioden": [],
                "Perioden_Bewertung": None
            }

        # 3. Perioden clustern basierend auf echten Handelstagen
        perioden = PeriodAnalysis.cluster_buy_signal_periods(kaufsignale_df, max_gap_days=5)

        # 4. Jede Periode bewerten
        perioden_bewertung = PeriodAnalysis.evaluate_buy_periods(perioden, full_data,
                                                Auswertung_tage=Auswertung_tage,
                                                min_veraenderung=min_veraenderung)

        # 5. Einzelbewertung (optional)
        einzelbewertung = PeriodAnalysis.evaluate_buy_signals(full_data, kaufsignale_df,
                                            Auswertung_tage=Auswertung_tage,
                                            min_veraenderung=min_veraenderung,
                                            )

        return {
            "Anzahl_Kaufsignale": len(kaufsignale_df),
            "Trefferquote_Kauf (%)": einzelbewertung["Trefferquote_Kauf (%)"],
            "Gesamt_Signale": len(signale_df),
            "Signal_Details": signale_df,
            "Perioden": perioden,
            "Perioden_Bewertung": perioden_bewertung,
            "Einzelbewertung": einzelbewertung
        }
    
    @staticmethod
    def analyse_kaufsignal_perioden_2(full_data: pd.DataFrame,
                                Auswertung_tage,
                                min_veraenderung,
                                Kategorie, TradingStatus,
                                min_len_window: int = 20,
                                innerhalb_zeitraum: bool = True):
        # 1. Alle Signale über den gesamten Zeitraum generieren
        signale_liste = []

        for i in range(min_len_window, len(full_data)):
            fenster = full_data.iloc[:i+1]
            entscheidung, einzelsignale, gesamtscore = SwingTrading.kombiniertes_signal_3(fenster, Kategorie, TradingStatus)  # Deine Signalgenerierung
            datum = fenster.index[-1]
            signale_liste.append({"Datum": datum, "Entscheidung": entscheidung, **einzelsignale})

        signale_df = pd.DataFrame(signale_liste)  # signale_df hier erzeugen!

        # 2. Nur Kaufsignale herausfiltern
        kaufsignale_df = signale_df[signale_df["Entscheidung"].str.contains("Kauf")].copy()

        if kaufsignale_df.empty:
            return {
                "Anzahl_Kaufsignale": 0,
                "Trefferquote_Kauf (%)": None,
                "Gesamt_Signale": 0,
                "Signal_Details": signale_df,
                "Perioden": [],
                "Perioden_Bewertung": None
            }

        # 3. Perioden clustern basierend auf echten Handelstagen
        perioden = PeriodAnalysis.cluster_buy_signal_periods(kaufsignale_df, max_gap_days=5)

        # 4. Jede Periode bewerten
        perioden_bewertung = PeriodAnalysis.evaluate_buy_periods(perioden, full_data,
                                                Auswertung_tage=Auswertung_tage,
                                                min_veraenderung=min_veraenderung)

        # 5. Einzelbewertung (optional)
        einzelbewertung = PeriodAnalysis.evaluate_buy_signals(full_data, kaufsignale_df,
                                            Auswertung_tage=Auswertung_tage,
                                            min_veraenderung=min_veraenderung,
                                            )

        return {
            "Anzahl_Kaufsignale": len(kaufsignale_df),
            "Trefferquote_Kauf (%)": einzelbewertung["Trefferquote_Kauf (%)"],
            "Gesamt_Signale": len(signale_df),
            "Signal_Details": signale_df,
            "Perioden": perioden,
            "Perioden_Bewertung": perioden_bewertung,
            "Einzelbewertung": einzelbewertung
        }

    def cluster_buy_signal_periods(kaufsignale_df: pd.DataFrame, max_gap_days: int = 5):
        if "Datum" not in kaufsignale_df.columns:
            kaufsignale_df = kaufsignale_df.reset_index()

        daten = kaufsignale_df.sort_values("Datum").reset_index(drop=True)["Datum"]

        perioden = []
        start = daten[0]
        prev = daten[0]

        for current in daten[1:]:
            diff = (current - prev).days
            if diff <= max_gap_days:
                prev = current
            else:
                perioden.append((start, prev))
                start = current
                prev = current
        perioden.append((start, prev))

        return perioden


    def evaluate_buy_periods(perioden, full_data,
                            Auswertung_tage, min_veraenderung):
        bewertungen = []

        for (start_datum, end_datum) in perioden:
            # jetzt sind start_datum und end_datum schon Datumswerte
            try:
                start_kurs = full_data.loc[end_datum, "Close"]
            except KeyError:
                bewertungen.append({
                    "Start_Datum": start_datum,
                    "End_Datum": end_datum,
                    "Bewertung": None,
                    "Kommentar": "Datum nicht in Daten gefunden"
                })
                continue

            try:
                end_index = full_data.index.get_loc(end_datum)
                lookahead_index = end_index + Auswertung_tage
                if lookahead_index >= len(full_data):
                    lookahead_index = len(full_data) - 1
                max_kurs = full_data.iloc[end_index:lookahead_index+1]["Close"].max()
            except Exception as e:
                bewertungen.append({
                    "Start_Datum": start_datum,
                    "End_Datum": end_datum,
                    "Bewertung": None,
                    "Kommentar": f"Fehler beim Kursvergleich: {e}"
                })
                continue

            kurs_diff = (max_kurs - start_kurs) / start_kurs
            getroffen = kurs_diff >= min_veraenderung

            bewertungen.append({
                "Start_Datum": start_datum,
                "End_Datum": end_datum,
                "Bewertung": getroffen,
                "Max_Kurs": max_kurs,
                "Start_Kurs": start_kurs,
                "Kurs_Diff": kurs_diff,
                "Kommentar": f"Kursanstieg >= {min_veraenderung*100:.1f}%: {getroffen}"
            })

        return bewertungen

    def evaluate_buy_signals(full_data, kaufsignale_df, Auswertung_tage, min_veraenderung):
        """
        Bewertet einzelne Kaufsignale nach Kursentwicklung.

        Parameter:
        - full_data: kompletter DataFrame mit Kursdaten
        - kaufsignale_df: DataFrame mit Kaufsignalen (mit Spalte 'Datum')
        - kombiniertes_signal: Funktion zur Signalgenerierung (optional für Erweiterungen)
        - Auswertung_tage: Anzahl der Tage, um Kursanstieg zu beobachten
        - min_veraenderung: Mindest-Kursanstieg für Treffer
        - min_len_window, innerhalb_zeitraum: Optional, falls für Erweiterungen

        Rückgabe:
        - Dict mit Trefferquote und Anzahl geprüfter Signale
        """

        treffer = 0
        anzahl = 0

        for _, signal_row in kaufsignale_df.iterrows():
            datum = signal_row["Datum"]

            try:
                start_kurs = full_data.loc[datum, "Close"]
            except KeyError:
                continue  # Datum nicht gefunden, überspringen

            try:
                start_index = full_data.index.get_loc(datum)
                end_index = start_index + Auswertung_tage
                if end_index >= len(full_data):
                    end_index = len(full_data) - 1
                max_kurs = full_data.iloc[start_index:end_index+1]["Close"].max()
            except Exception:
                continue

            kurs_diff = (max_kurs - start_kurs) / start_kurs
            if kurs_diff >= min_veraenderung:
                treffer += 1
            anzahl += 1

        trefferquote = (treffer / anzahl * 100) if anzahl > 0 else None

        return {
            "Trefferquote_Kauf (%)": trefferquote,
            "Anzahl_geprüfter_Signale": anzahl,
            "Treffer": treffer
        }
    
    def plot_priodenchart(self, data, symbol, version, kaufperioden=None):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines", name="Schlusskurs", line=dict(color="blue")))
        
        fig.add_trace(go.Scatter(x=data.index, y=data["BB_Upper"], mode="lines", line=dict(dash='dash'), name="BB Oberband"))
        fig.add_trace(go.Scatter(x=data.index, y=data["BB_Lower"], mode="lines", line=dict(dash='dash'), name="BB Unterband"))

        # Kaufperioden als grüne Bereiche einzeichnen
        if kaufperioden is not None and not kaufperioden.empty:
            for _, row in kaufperioden.iterrows():
                    # Farbe je nach Signal
                    if row["Signal"]:
                        fill_color = "green"
                        line_color = "green"
                    else:
                        fill_color = "lightgrey"  # hellgrau für "false"
                        line_color = "grey"
                    fig.add_vrect(
                        x0=row["Start"],
                        x1=row["Ende"],
                        fillcolor=fill_color,
                        opacity=0.2,
                        layer="below",
                        line_width=0,
                    )
                    # Optional: Kursverlauf in der Kaufperiode grün färben
                    periode_mask = (data.index >= row["Start"]) & (data.index <= row["Ende"])
                    fig.add_trace(go.Scatter(
                        x=data.index[periode_mask],
                        y=data["Close"][periode_mask],
                        mode="lines",
                        line=dict(color=line_color, width=3),
                        name="Kaufperiode",
                        showlegend=False
                    ))
        fig.update_layout(xaxis_title="Datum", yaxis_title="Preis (USD)", 
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.05,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.3)",
            bordercolor="rgba(0,0,0,0.15)",
            borderwidth=1
        ))
        st.plotly_chart(fig, use_container_width=True, key=f"Periodenchart_{version}")


"""
Weitere Ideen: Einführung eines adaptiven framework, das die Gewichtung der Indikatoren aus historischer Analysen anpasst.

"""
