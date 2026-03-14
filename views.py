import streamlit as st
import plotly.graph_objects as go
import pandas as pd

class TechnicalMetrics:
    def show_technical_metrics(self, data, st_output, title="📋 Technische Kennzahlen"):
        """Erstellt eine Tabelle der wichtigsten technischen Kennzahlen."""

        st_output.subheader(title)

        letzte = data.iloc[-1]
        kennzahlen = {}

        # 1️⃣ Erste Gruppe von Indikatoren
        erste_gruppe = [
            "Close", "MA10", "MA50", "RSI", "ATR",
            "BB_Upper", "BB_Lower", "MACD", "MACD_Signal"
        ]

        for key in erste_gruppe:
            if key in data.columns:
                val = letzte[key]
                if key in ["MACD", "MACD_Signal"]:
                    kennzahlen[key] = [round(val, 4)]
                else:
                    kennzahlen[key] = [round(val, 2)]

        # 2️⃣ Zweite Gruppe von Indikatoren
        zweite_gruppe = [
            "Stoch_%K", "Stoch_%D", "ADX", "+DI", "-DI",
            "Tenkan_sen", "Kijun_sen"
        ]

        for key in zweite_gruppe:
            if key in data.columns:
                val = letzte[key]
                if pd.isna(val):
                    kennzahlen[key] = ["N/A"]
                else:
                    kennzahlen[key] = [round(val, 2)]

        # 3️⃣ DataFrame erzeugen
        kennzahlen_df = pd.DataFrame.from_dict(
            kennzahlen,
            orient="index",
            columns=["Wert"]
        )

        # String-Konvertierung für saubere Ausgabe
        kennzahlen_df = kennzahlen_df.astype(str)

        # 4️⃣ Anzeige
        st_output.table(kennzahlen_df)

    def zeige_fundamentaldaten(self, fundamentaldaten):
        """Lädt Fundamentaldaten für ein Symbol und zeigt sie als Tabelle in Streamlit an."""

        st.subheader("🏦 Fundamentaldaten")

        if fundamentaldaten:
            # In DataFrame umwandeln
            fundamentaldaten_df = pd.DataFrame(
                list(fundamentaldaten.items()),
                columns=["Kennzahl", "Wert"]
            ).astype(str)

            st.table(fundamentaldaten_df)

        else:
            st.warning("Keine Fundamentaldaten gefunden.")

class MainDataAnalyzer:
    def __init__(self, data):
        self.data = data

    def plot_hautpchart(self, name, version):
        data = self.data
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["MA10"], mode="lines", name="MA10"))
        fig.add_trace(go.Scatter(x=data.index, y=data["MA50"], mode="lines", name="MA50"))
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines", name="Schlusskurs"))
        fig.add_trace(go.Scatter(x=data.index, y=data["BB_Upper"], mode="lines", line=dict(dash='dash'), name="BB Oberband"))
        fig.add_trace(go.Scatter(x=data.index, y=data["BB_Lower"], mode="lines", line=dict(dash='dash'), name="BB Unterband"))

        #if show_pivotsif opt["bollinger"]
        #    for col, color, name in [("Support1", "green", "Support 1"), ("Support2", "green", "Support 2"),
        #                             ("Resistance1", "red", "Resistance 1"), ("Resistance2", "red", "Resistance 2")]:
        #        if col in data.columns:
        #            fig.add_trace(go.Scatter(x=data.index, y=data[col], mode="lines", line=dict(dash='dot', color=color), name=name))
        fig.update_layout(
            xaxis_title="Datum",
            yaxis_title="Preis (USD)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.3)",
                bordercolor="rgba(0,0,0,0.15)",
                borderwidth=1
            )
        )
        st.subheader(f"{name} Kurs")
        st.plotly_chart(fig, use_container_width=True, key=f"hauptchart_{version}")

    def plot_MA(self, name, version):
        data = self.data
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines", name="Schlusskurs"))
        fig.add_trace(go.Scatter(x=data.index, y=data["MA10"], mode="lines", name="MA10"))
        fig.add_trace(go.Scatter(x=data.index, y=data["MA50"], mode="lines", name="MA50"))
       
        fig.update_layout(
            xaxis_title="Datum",
            yaxis_title="Preis (USD)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.3)",
                bordercolor="rgba(0,0,0,0.15)",
                borderwidth=1
            )
        )
        #st.subheader(f"{name} Kurs")
        st.plotly_chart(fig, use_container_width=True, key=f"MA_{version}")

    def plot_bollinger(self, name, version):
        data = self.data
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines", name="Schlusskurs"))

        fig.add_trace(go.Scatter(x=data.index, y=data["BB_Upper"], mode="lines", line=dict(dash='dash'), name="BB Oberband"))
        fig.add_trace(go.Scatter(x=data.index, y=data["BB_Lower"], mode="lines", line=dict(dash='dash'), name="BB Unterband"))

        fig.update_layout(
            xaxis_title="Datum",
            yaxis_title="Preis (USD)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.3)",
                bordercolor="rgba(0,0,0,0.15)",
                borderwidth=1
            )
        )
        #st.subheader(f"{name} Kurs")
        st.plotly_chart(fig, use_container_width=True, key=f"bollinger_{version}")

class indikatoren_databoards:
    def rsi_databoard(self, latest, history):
        st.subheader("📉 RSI Analyse")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Aktueller RSI",
            latest["value"],
            latest["label"]
        )

        col2.metric(
            "Oversold (%)",
            f"{history['oversold_pct']} %"
        )

        col3.metric(
            "Overbought (%)",
            f"{history['overbought_pct']} %"
        )

    def macd_databoard(self, letzter_hist, letzter_signal, letzter_macd):
        st.subheader("📉 MACD Analyse")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Histogram",
            round(letzter_hist, 4),
            "label"
        )

        col2.metric(
            "Aktueller Signalwert:",
            round(letzter_signal, 4)
        )

        col3.metric(
            "Aktueller MACD Wert:",
            round(letzter_macd, 4)
        )

class indikatoren_plot:
    def plot_rsi(self, data, symbol):
        rsi_fig = go.Figure()
        rsi_fig.add_trace(go.Scatter(x=data.index, y=data["RSI"], mode="lines", name="RSI"))
        rsi_fig.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="Überverkauft (30)", annotation_position="bottom left")
        rsi_fig.add_hline(y=45, line_dash="dash", line_color="grey", annotation_text="Neutral (Lower Limit)", annotation_position="bottom left")
        rsi_fig.add_hline(y=55, line_dash="dash", line_color="grey", annotation_text="Neutral (Upper Limit)", annotation_position="top left")
        rsi_fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Überkauft (70)", annotation_position="top left")
        rsi_fig.update_layout(title=f"Actual RSI Chart", xaxis_title="Datum", yaxis_range=[0, 100], 
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
        st.plotly_chart(rsi_fig, use_container_width=True)

    def plot_macd(self, data, symbol):
        macd_fig = go.Figure()
        macd_fig.add_trace(go.Scatter(x=data.index, y=data["MACD"], mode="lines", name="MACD"))
        macd_fig.add_trace(go.Scatter(x=data.index, y=data["MACD_Signal"], mode="lines", name="Signal"))
        macd_fig.add_trace(go.Bar(x=data.index, y=data["MACD_Hist"], name="Histogramm"))
        macd_fig.update_layout(title=f"{symbol} MACD", xaxis_title="Datum", legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.3)",
                bordercolor="rgba(0,0,0,0.15)",
                borderwidth=1
            ))
        st.plotly_chart(macd_fig, use_container_width=True)

    def plot_stoch(self, data, symbol):
        stoch_fig = go.Figure()
        stoch_fig.add_trace(go.Scatter(x=data.index, y=data["Stoch_%K"], mode="lines", name="%K"))
        stoch_fig.add_trace(go.Scatter(x=data.index, y=data["Stoch_%D"], mode="lines", name="%D"))
        stoch_fig.update_layout(title=f"{symbol} Stochastic Oscillator", xaxis_title="Datum", yaxis_range=[0, 100], 
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
        st.plotly_chart(stoch_fig, use_container_width=True)

    def plot_adx(self, data, symbol):
        adx_fig = go.Figure()
        adx_fig.add_trace(go.Scatter(x=data.index, y=data["ADX"], mode="lines", name="ADX"))
        adx_fig.add_trace(go.Scatter(x=data.index, y=data["+DI"], mode="lines", name="+DI"))
        adx_fig.add_trace(go.Scatter(x=data.index, y=data["-DI"], mode="lines", name="-DI"))
        adx_fig.update_layout(title=f"{symbol} ADX", xaxis_title="Datum",
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
        st.plotly_chart(adx_fig, use_container_width=True)

class IchimokuAnalyer:
    def plot_Ichimoku(self, data, symbol):
        # Figure MUSS existieren
        fig = go.Figure()

        # Ichimoku-Linien
        lines = [
            ("Tenkan_sen", "Tenkan-sen", "solid", "blue"),
            ("Kijun_sen", "Kijun-sen", "solid", "orange"),
            ("Senkou_Span_A", "Senkou Span A", "dash", "green"),
            ("Senkou_Span_B", "Senkou Span B", "dash", "red"),
            ("Chikou_Span", "Chikou Span", "dot", "purple"),
        ]

        for col, line_name, line_style, line_color in lines:
            if col in data.columns:
                fig.add_trace(go.Scatter(
                    x=data.index,
                    y=data[col],
                    mode="lines",
                    line=dict(dash=line_style, color=line_color),
                    name=line_name
                ))

        fig.update_layout(
            title=f"Ichimoku – {symbol}",
            xaxis_title="Datum",
            yaxis_title="Preis",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.3)",
                bordercolor="rgba(0,0,0,0.15)",
                borderwidth=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)