import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from signals_generation import (
    FundamentalAnalysis,
    Analystenbewertung,
    SwingTrading,
    PeriodAnalysis
)

from SwingtradingSignale import(
    RSIAnalysis,
    MACDAnalysis,
    MACDAnalysis_Confirmations,
    ADXAnalysis,
    MAAnalysis,
    BollingerAnalysis,
    StochasticAnalysis,
    ATRQualityAnalysis,
    MarketRegimeAnalysis,
    EntryQualityAnalysis,
    TradeDecisionEngine,
    PositionSizer,
    SwingSignalService
)

from views import(
    TechnicalMetrics,
    MainDataAnalyzer,
    indikatoren_databoards,
    indikatoren_plot,
    IchimokuAnalyer
)

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

from signals_2 import (
    analyse_kaufsignal_perioden
)

from config.thresholds import (
    get_thresholds
)

def go_to(page_name):
    st.session_state.page = page_name

def home_page():
    watchlist = lade_aktien()
    # --------------------------------------------------
    # SIDEBAR – Watchlist verwalten
    # --------------------------------------------------
    with st.sidebar:
        # --------------------------------------------------
        # Aktie zu Watchlist hinzufügen
        # --------------------------------------------------
        st.subheader("📌 Watchlist verwalten")
        symbols_existing = [w["symbol"] for w in watchlist]

        st.markdown("### ➕ Aktie hinzufügen")
        new_name = st.text_input("Unternehmensname")
        new_symbol = st.text_input("Ticker / Symbol in yFinance").upper()

        if st.button("Zur Watchlist hinzufügen"):
            if not new_name or not new_symbol:
                st.warning("Bitte Name und Symbol angeben")
            elif new_symbol in symbols_existing:
                st.warning("Symbol ist bereits in der Watchlist")
            else:
                watchlist.append({
                    "name": new_name.strip(),
                    "symbol": new_symbol.strip()
                })
                save_watchlist_json(watchlist)
                st.cache_data.clear()  # Cache löschen!
                st.success(f"{new_symbol} hinzugefügt")
                try:
                    st.experimental_rerun()
                except AttributeError:
                    st.rerun()

        # ------------------------------------------------------
        # Aktie aus Watchlist entfernen
        # ------------------------------------------------------
        st.markdown("### ❌ Aktie entfernen")
        remove_symbol = st.selectbox(
            "Symbol auswählen",
            [""] + symbols_existing
        )
        if st.button("Aus Watchlist entfernen") and remove_symbol:
            watchlist = [
                w for w in watchlist if w["symbol"] != remove_symbol
            ]
            save_watchlist_json(watchlist)
            st.cache_data.clear()  # Cache löschen!
            st.success(f"{remove_symbol} entfernt")
            try:
                st.experimental_rerun()
            except AttributeError:
                st.rerun()

    # ------------------------------------------------------
    # Aktie Auswahl Button mit Links auflisten
    # ------------------------------------------------------
    st.title("📈 Aktien-Dashboard")
    st.write("Wähle eine Aktie:")
    for i, w in enumerate(watchlist):
        name = w["name"]
        symbol = w["symbol"]
        if st.button(f"{name} ({symbol})", key=f"button_{symbol}_{i}"):
            st.session_state.page = (name, symbol)  # Tuple speichern

def aktienseite(): 
    name, symbol = st.session_state.page
    # ---------------------------------------------------------
    # Sidebar-Parameter laden
    # ---------------------------------------------------------  
    tage, min_veraenderung, Auswertung_tage, short_window, long_window, signal_window = lade_sidebar_parameter()
        
    # ---------------------------------------------------------
    # Laden aller Daten der letzten 4 jahre für weitere 
    # grundlegende Berechnungen und Anzeigen
    # ---------------------------------------------------------
    max_period = "4y"
    try:
        data_full = lade_daten_aktie(symbol, period=max_period)
        data_full = berechne_indikatoren(data_full)
    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
        return
    
    # Startdatum berechnen (heute minus tage)
    startdatum = pd.Timestamp.today(tz=data_full.index.tz) - pd.Timedelta(days=tage)
    # Daten filtern, nur Daten ab Startdatum behalten
    data = data_full.loc[data_full.index >= startdatum]
    # ---------------------------------------------------------
    # Aufrunf der Klassenfunktionen
    # ---------------------------------------------------------
    technicalmetrics = TechnicalMetrics()
    fundamental_alanalyzer = FundamentalAnalysis()
    main_analyzer = MainDataAnalyzer(data)
    Ichimoku_analyzer = IchimokuAnalyer()
    Swingtrading = SwingTrading()
    Analysten = Analystenbewertung()
    period_analyzer = PeriodAnalysis()

    # ---------------------------------------------------------

    rsi_analysis = RSIAnalysis(
        oversold=thresholds["RSI"]["oversold"],
        overbought=thresholds["RSI"]["overbought"],
        bullish_floor=thresholds["RSI"]["bullish_floor"],
        bearish_ceiling=thresholds["RSI"]["bearish_ceiling"],
    )

    macd_analysis = MACDAnalysis()  # unverändert
    adx_analysis = ADXAnalysis(
        weak_trend=thresholds["ADX"]["weak_trend"],
        strong_trend=thresholds["ADX"]["strong_trend"],
        extreme_trend=thresholds["ADX"]["extreme_trend"],
    )
    macd_zwei_analysis = MACDAnalysis_Confirmations()
    adx_analysis = ADXAnalysis()
    ma_analysis = MAAnalysis()
    bollinger_analysis = BollingerAnalysis()
    stochastic_analysis = StochasticAnalysis()
    market_analysis = MarketRegimeAnalysis()
    atr_analysis = ATRQualityAnalysis()
    entryquality_analysis = EntryQualityAnalysis()
    trade_decision = TradeDecisionEngine()
    swingsignal_analysis = SwingSignalService()
    indikatoren_boards = indikatoren_databoards()
    indikatoren_diagram = indikatoren_plot()

    # ---------------------------------------------------------
    # Laden und Analysieren der Fundamentaldaten
    # ---------------------------------------------------------  
    fundamentaldaten = lade_fundamentaldaten(symbol)
    data_fund = fundamental_alanalyzer.fundamental_analyse(fundamentaldaten, symbol)
    sector = fundamentaldaten.get("sector")  # kann "Unknown" sein
    thresholds = get_thresholds(symbol=symbol, sector=sector)


    # ---------------------------------------------------------
    # Import der Analysten Daten
    # ---------------------------------------------------------  
    analysten_daten = lade_analystenbewertung(symbol)
    summary_df = analysten_daten["summary"]
    rating_counts = Analysten.berechne_rating_bar(summary_df)

    # ---------------------------------------------------------
    # Klassifizierung der Aktie
    # ---------------------------------------------------------  
    klassifikation = klassifiziere_aktie(symbol, data_full, fundamentaldaten)
    erklaerung = erklaere_kategorien(klassifikation["Profil"], klassifikation["Trading_Status"])

    # ---------------------------------------------------------
    # Indikatorenauswertung
    # --------------------------------------------------------- 
    rsi_result = rsi_analysis.analyse(data)
    rsi_latest = {"value": rsi_result["value"], "label": rsi_result["state"]}
    rsi_history = rsi_analysis.analyze_history(data)
    rsi_interp = rsi_result["interpretation"]
    macd_result = macd_analysis.analyse(data)
    macd_interp = macd_result["interpretation"]
    macd_zwei_result = macd_zwei_analysis.analyse(data)
    macd_zwei_interp = macd_zwei_result["interpretation"]
    adx_result = adx_analysis.analyse(data)
    ma_result = ma_analysis.analyse(data)
    bollinger_result = bollinger_analysis.analyze(data)
    stochastic_result = stochastic_analysis.analyze(data)
    atr_14 = atr_analysis.calculate_atr(data)
    # Analyse für den letzten Kurs
    atr_result = atr_analysis.analyse(
        current_price = data["Close"].iloc[-1],
        atr = data["ATR"].iloc[-1],
        ma50 = data["MA50"].iloc[-1],
        ma10 = data["MA10"].iloc[-1]
    )
    market_result = market_analysis.analyse(rsi_result, macd_result, adx_result, ma_result)
    entryquality_result = entryquality_analysis.analyse(bollinger_result, stochastic_result, market_result, ma_result, atr_result)
    tradedecision_result = trade_decision.decide(market_result, rsi_result, macd_result, adx_result)
    swingsignal_analysed = swingsignal_analysis.run_analysis(data, Auswertung_tage, min_veraenderung, market_result, rsi_result, macd_result, adx_result)
   
    # ---------------------------------------------------------
    # Überschrift der Aktienseite
    # ---------------------------------------------------------
    col1, col2 = st.columns([2, 1])
    with col1:
        st.title(f"📊 {name} – Analyse")
    with col2: 
        # Navigation zurück
        st.write("") #Leerzeile für Format
        st.write("") #Leerzeile für Format
        if st.button("⬅️ Zurück zur Startseite"):
            go_to("home")

    # ---------------------------------------------------------
    # Definition der TABS
    # ---------------------------------------------------------
    tab_overview, tab_charts, tab_handel, tab_ichimoku, tab_fundamentals, tab_rsi, Algorithmus = st.tabs(
        ["📈 Übersicht", "📊 Charts", "🔔Handelsentscheidung", "🌥️ Ichimoku", "🏦 Fundamentaldaten", "RSI", "Algorithmus"]
    )
    # ---------------------------------------------------------
    # TAB Overview
    # ---------------------------------------------------------
    with tab_overview:
        with st.container(border=True):
            main_analyzer.plot_hautpchart(name, 1)
        # --- 2 Spalten Layout ---
        col1, col2 = st.columns([1, 1])

        # --- 1️⃣ LINKE SPALTE ---
        with col1:
            with st.container(border=True):
                st.subheader("📌 Klassifizierung der Aktie:")
                st.metric("Profil:", klassifikation["Profil"])
                st.metric("Trading Status:", klassifikation["Trading_Status"])
                with st.expander("Details zur Aktien-Kathegorie:"):
                    st.write(erklaerung)

        # --- 2️⃣ RECHTE SPALTE ---
        with col2:
            with st.container(border=True):
                st.subheader("Experteneinschätzung:")
                if summary_df is not None:
                    Analysten.zeichne_rating_gauge(rating_counts)

        # --- 2 Spalten Layout ---
        col1, col2, col3 = st.columns([1,1,1])

        # --- 1️⃣ LINKE SPALTE ---
        with col1:
            with st.container(border=True):
                st.subheader("🏦 Fundamental Übersicht:")
                fundamental_alanalyzer.fundamental_summary(data_fund)
            

        # --- 2️⃣ MITTLERE SPALTE ---
        with col2:
            with st.container(border=True):   
                st.subheader("🔄 Swingtrading Übersicht:")
                if tradedecision_result["action"] == "BUY":
                    st.success(f"Kaufe Aktien") #{pos['position_size']}
                else:
                    st.error(f"Kein Trade")

                zeige_swingtrading_signalauswertung(data, swingsignal_analysed)

        # --- 2️⃣ RECHTE SPALTE ---
        with col3:
            with st.container(border=True):   
                st.subheader("Indikatorenauswertung:")             
                st.markdown(
                    f"- **RSI:** {rsi_interp['meaning']}\n"
                    f"- **MACD:** {macd_interp['meaning']}\n"
                    f"- **Stochastics:** {stochastic_result['summary']}\n"
                    f"- **ADX:** {adx_result['trend_acceleration']}"
                    )

    # ---------------------------------------------------------
    # TAB CHARTS
    # ---------------------------------------------------------
    with tab_charts:
        col1, col2 = st.columns([1,1])
        with col1:
            with st.container(border=True):
                st.subheader("MA10 und MA50 Analyse")
                main_analyzer.plot_MA(name, 1)
        with col2:
            with st.container(border=True):
                st.subheader("Bollinger Analyse")
                main_analyzer.plot_bollinger(name, 1)
                st.metric("Volatilität (Bollinger Bandbreite):", f"{bollinger_result['bandwidth']:.2f}")
                st.info(f"Zusammenfassung: {bollinger_result["summary"]}")
                st.info(f"Interpretation: {bollinger_result["interpretation_long"]}")
                col11, col12 = st.columns(2)
                with col11:
                    st.success(f"Chance: {bollinger_result['chance']}")
                with col12:
                    st.warning(f"Risiko: {bollinger_result['risk']}")
                st.write()
                st.info(f"Handlungsfazit: {bollinger_result['action_hint']}")

        col1, col2 = st.columns([1,1])
        # ---------------------------------------------------------
        # 1️⃣ LINKE SPALTE
        # ---------------------------------------------------------
        with col1:
            with st.container(border=True):
                indikatoren_boards.rsi_databoard(rsi_latest, rsi_history)
                indikatoren_diagram.plot_rsi(data, symbol)
                #rsi_text = (f"Regime: {rsi_result['regime']}\n" f"State: {rsi_result['state']}\n" f"Bias: {rsi_result['bias']}")
                st.markdown(f"### RSI – {rsi_interp['headline']}")
                st.info(f"Interpretation: {rsi_interp["meaning"]}")
                col11, col12 = st.columns(2)
                with col11:
                    st.success(f"Chance: {rsi_interp['chance']}")
                with col12:
                    st.warning(f"Risiko: {rsi_interp['risk']}")
                st.info(f"Handlungsfazit: {rsi_interp['typical_action']}")
                st.progress(int(round(rsi_result["strength"] * 100)))
        # ---------------------------------------------------------
        # 2️⃣ RECHTE SPALTE
        # ---------------------------------------------------------
        with col2:
            with st.container(border=True):
                # MACD Chart
                indikatoren_boards.macd_databoard(macd_result["histogram"], macd_result["signal"], macd_result["macd"])
                #macd_analyzer.plot_macd(data, symbol)
                indikatoren_diagram.plot_macd(data, symbol)
                macd_text = (f"Regime: {macd_result['regime']}\n" f"State: {macd_result['state']}\n" f"Bias: {macd_result['bias']}")
                st.text_area("MACD Interpretation", macd_text, key=f"macd_interpretation_{name}")
                st.markdown(f"### MACD – {macd_interp['headline']}")
                st.info(f"Interpretation: {macd_interp["meaning"]}")
                col11, col12 = st.columns(2)
                with col11:
                    st.success(f"Chance: {macd_interp['chance']}")
                with col12:
                    st.warning(f"Risiko: {macd_interp['risk']}")
                st.info(f"Handlungsfazit: {macd_interp['typical_action']}")
                st.progress(int(round(macd_result["strength"] * 100)))

        col1, col2 = st.columns([1,1])
        with col2:
            with st.container(border=True):
                # MACD Chart
                indikatoren_boards.macd_databoard(macd_zwei_result["histogram"], macd_zwei_result["signal"], macd_zwei_result["macd"])
                #macd_analyzer.plot_macd(data, symbol)
                #indikatoren_diagram.plot_macd(data, symbol)
                macd_text = (f"Regime: {macd_zwei_result['regime']}\n" f"State: {macd_zwei_result['state']}\n" f"Bias: {macd_zwei_result['bias']}")
                st.text_area("MACD Interpretation", macd_text, key=f"macd_interpretation1_{name}")
                st.markdown(f"### MACD – {macd_zwei_interp['headline']}")
                st.info(f"Interpretation: {macd_zwei_interp["meaning"]}")
                col11, col12 = st.columns(2)
                with col11:
                    st.success(f"Chance: {macd_zwei_interp['chance']}")
                with col12:
                    st.warning(f"Risiko: {macd_zwei_interp['risk']}")
                st.info(f"Handlungsfazit: {macd_zwei_interp['typical_action']}")
                st.progress(int(round(macd_result["strength"] * 100)))
                        
        col1, col2 = st.columns([1,1])
        # ---------------------------------------------------------
        # 1️⃣ LINKE SPALTE
        # ---------------------------------------------------------
        with col1:
            with st.container(border=True):
                # Stochastic Oscillator Chart
                st.subheader("Stochastics Analyse")
                indikatoren_diagram.plot_stoch(data, symbol)
                st.info(f"Zusammenfassung: {stochastic_result['summary']}")
                st.text_area("Stochastics Zusammenfassung:", stochastic_result['summary'], key=f"stochastics_zusammenfassung_{name}")
                st.markdown(f"### RSI – {stochastic_result['interpretation_short']}")
                st.info(f"Interpretation: {stochastic_result["interpretation_long"]}")
                st.write()
                col11, col12 = st.columns(2)
                with col11:
                    st.success(f"Chance: {bollinger_result['chance']}")
                with col12:
                    st.warning(f"Risiko: {bollinger_result['risk']}")
                st.info(f"Handlungsfazit: {stochastic_result['action_hint']}")
        
        # ---------------------------------------------------------
        # 2️⃣ RECHTE SPALTE
        # ---------------------------------------------------------
        with col2:
            with st.container(border=True):
                st.subheader("ADX Analyse")
                indikatoren_diagram.plot_adx(data, symbol)
                adx_text = (f"Regime: {adx_result['regime']}\n" f"State: {adx_result['state']}\n" f"Bias: {adx_result['bias']}")
                st.text_area("ADX Interpretation", adx_text, key=f"adx_interpretation_{name}")
                st.markdown(f"### ADX – {adx_result['interpretation_short']}")
                st.metric(adx_result["interpretation_short"], adx_result["trend_acceleration"])
                st.info(f"Interpretation: {adx_result['interpretation_long']}")
                col11, col12 = st.columns(2)
                with col11:
                    st.success(f"Chance: {adx_result['chance']}")
                with col12:
                    st.warning(f"Risiko: {adx_result['risk']}")
                st.info(f"Handlungsfazit: {adx_result['action_hint']}")
                st.progress(int(round(adx_result["strength"] * 100)))

    
    with tab_handel:
        # ---------------------------------------------------------
        # 2️⃣ RECHTE SPALTE
        # ---------------------------------------------------------
        with st.container(border=True):
            # Regime-spezifische ATR-Multiplikatoren aus der Zentrale
            regime_mults = thresholds["ATR_MULTS"].get(regime, thresholds["ATR_MULTS"]["default"])
            
            # SL/TP berechnen – jetzt mit externen Multiplikatoren
            sl_tp = trm.sl_tp_by_atr(
                atr=atr,
                position_typ=position_typ,
                mults=regime_mults
            )
            st.markdown(f"### Handelsentscheidung – {tradedecision_result['interpretation_short']}")
    
            # --- ATR-basierte SL/TP via TradeRiskManager ---
            atr = float(data["ATR"].iloc[-1])
            letzter_close = float(data["Close"].iloc[-1])
            regime = market_result.get("market_regime")  # "trend_market", "range_market", etc.
    
            # Wichtig: TradeRiskManager muss importiert sein (oben im File oder hier lokal)
            from SwingtradingSignale import TradeRiskManager
    
            # Richtung ableiten aus der Entscheidung
            position_typ = "long" if tradedecision_result["action"] == "BUY" else "short"
    
            # SL/TP berechnen (ATR-basiert, Regime-sensitiv)
            trm = TradeRiskManager(einstiegskurs=letzter_close, regime=regime)
            sl_tp = trm.stop_loss_take_profit(
                position_typ=position_typ,
                use_atr=True,
                atr=atr
            )
    
            stop_loss_kurs_berechnet = sl_tp["stop_loss"]
            take_profit_kurs_berechnet = sl_tp["take_profit"]
    
            # Positionsgröße nur bei BUY (Long) berechnen und anzeigen
            if tradedecision_result["action"] == "BUY":
                sizer = PositionSizer(konto_groesse=10000)
                pos = sizer.berechne_positionsgroesse(
                    einstiegskurs=letzter_close,
                    stop_loss_kurs=stop_loss_kurs_berechnet,
                    risiko_prozent=1.0,
                    confidence=tradedecision_result["confidence"],
                    risiko_level=tradedecision_result["risk_level"]
                )
    
                st.success(f"Kaufe {pos['position_size']} Aktien")
                st.info(f"Riskamount: {pos['risk_amount']}")
                st.info(f"Stop-Loss-Abstand: {pos['stop_loss_abstand']}")
                st.progress(int(round(tradedecision_result["confidence"] * 100)))
    
            else:
                # Für SELL/WAIT/HOLD/REDUCE etc.: keine Positionsgröße,
                # aber SL/TP-Vorschlag und klare Aussage
                st.error("Kein Long-Trade (BUY) – aktuelle Entscheidung: "
                         f"{tradedecision_result['action']}")
                # Falls du hier Short-Trades später ausbauen willst,
                # kannst du analog eine Positionsgröße für Short ergänzen.
    
            # --- Gemeinsame Anzeige: ATR-SL/TP, Regime & Decision-Kontext ---
            st.markdown(
                f"**ATR‑SL/TP:** "
                f"SL = {stop_loss_kurs_berechnet:.2f} (×{sl_tp.get('sl_mult_atr', '?')} ATR), "
                f"TP = {take_profit_kurs_berechnet:.2f} (×{sl_tp.get('tp_mult_atr', '?')} ATR), "
                f"Regime = {regime}"
            )
    
            # --- Deine Info-Boxen: immer anzeigen, unabhängig von BUY/SELL ---
            st.info(f"Risk-Level: {tradedecision_result['risk_level']}")
            st.info(f"Zusammenfassung: {tradedecision_result['summary']}")
            st.info(f"Interpretation: {tradedecision_result['interpretation_long']}")
            st.warning(f"Handlungsfazit: {tradedecision_result['action_hint']}")


        with st.container(border=True):
                st.markdown(f"### Handelsentscheidung – Über eingestellten AUSWERTUNG TAGE mit eingestellten MINDESTKURSANSTIEG")
                zeige_swingtrading_signalauswertung(data, swingsignal_analysed)

        with st.container(border=True):
            st.markdown(f"### Entscheidungsgrundlage – {tradedecision_result["interpretation_short"]}")
            entscheidung_text = (f"Entscheidung: {tradedecision_result["action"]}\n" f"Position: {tradedecision_result["position_type"]}\n" f"Risiko: {tradedecision_result["risk_level"]}\n" f"Entscheidungsgrundlage: {tradedecision_result["reason"]}\n")
            st.text_area("Entscheidung Interpretation", entscheidung_text, key=f"Entscheidung_interpretation_{name}")
            st.info(f"Zusammenfassung: {tradedecision_result['summary']}")
            st.info(f"Interpretation: {tradedecision_result["interpretation_long"]}")
            st.warning(f"Handlungsfazit: {tradedecision_result['action_hint']}")
            st.progress(int(round(tradedecision_result["confidence"] * 100)))
        
        col1, col2 = st.columns([1,1])
        # ---------------------------------------------------------
        # LINKE SPALTE
        # ---------------------------------------------------------
        with col1:
            with st.container(border=True):
                st.markdown(f"### Markt Analyse – {market_result["interpretation_short"]}")
                market_text = (f"Regime: {market_result["market_regime"]}\n" f"Bias: {market_result["trade_bias"]}")
                st.text_area("Markt Interpretation", market_text, key=f"market_interpretation_{name}")
                st.info(f"Zusammenfassung: {market_result['summary']}")
                st.info(f"Interpretation: {market_result['interpretation_long']}")
                st.warning(f"Handlungsfazit: {market_result['action_hint']}")
                st.progress(int(round(market_result["confidence"] * 100)))

        with col2:
            with st.container(border=True):
                st.markdown(f"### Eintritt Analyse (Qualität) – {entryquality_result["interpretation_short"]}")
                st.info(f"Zusammenfassung: {entryquality_result["summary"]}")
                st.info(f"Interpretation: {entryquality_result["interpretation_long"]}")
                st.warning(f"Handlungsfazit: {entryquality_result['action_hint']}")
                st.write(entryquality_result["interpretation"])

        

    with tab_ichimoku:
        # ---------------------------------------------------------
        # Hauptchart
        # ---------------------------------------------------------
        Ichimoku_analyzer.plot_Ichimoku(data, name)


    with tab_fundamentals:
        with st.container(border=True):
            st.subheader("🏦 Übersicht des Fundamentalsignals")
            fundamental_alanalyzer.fundamental_interpretation(data_fund)

        col1, col2 = st.columns([1,1])
        # ---------------------------------------------------------
        # 1️⃣ LINKE SPALTE
        # ---------------------------------------------------------
        with col1:
            # Technische Kennzahlen als Tabelle
            technicalmetrics.show_technical_metrics(data, st, title="🔎 Wichtige Marktindikatoren")

        # ---------------------------------------------------------
        # 2️⃣ MITTLERE SPALTE
        # ---------------------------------------------------------
        with col2:
            # Fundamentaldaten
            technicalmetrics.zeige_fundamentaldaten(fundamentaldaten)

    with tab_rsi:  
        st.write("Leere Dummy Seite")
                
    with Algorithmus:
        st.write("Leere Dummy Seite")
        """
        with st.container(border=True):
            st.subheader("Analyse der Signale")
            zeige_kaufsignal_analyse(data, Auswertung_tage, min_veraenderung) 
            st.subheader("🔄 Swingtrading Übersicht:")
            Swingtrading.zeige_swingtrading_signalauswertung(data, Auswertung_tage, min_veraenderung, klassifikation["Profil"], klassifikation["Trading_Status"])
            st.subheader("🔄 Swingtrading Übersicht:")
            Swingtrading.zeige_swingtrading_signalauswertung_2(data, Auswertung_tage, min_veraenderung, klassifikation["Profil"], klassifikation["Trading_Status"])

        with st.container(border=True):
            analyse_ergebnis = analyse_kaufsignal_perioden(data, Auswertung_tage, min_veraenderung)
            # macht es nicht Sinn, die folgende Formatierung in die Funktion mit aufzunehmen?
            df_details = pd.DataFrame(analyse_ergebnis["Perioden_Bewertung"])
            df_details.columns = ["Start", "Ende", "Signal", "Wert1", "Wert2", "Beschreibung", "ExtraInfo"]
            df_details["Signal"] = df_details["Signal"].astype(str).str.upper() == "TRUE"
            df_details["Start"] = pd.to_datetime(df_details["Start"])
            df_details["Ende"] = pd.to_datetime(df_details["Ende"])
            st.subheader("Kennzeichnung der Original-Perioden")
            plot_priodenchart(data, name, 2, kaufperioden=df_details)
        
        with st.container(border=True):
            analyse_ergebnis = period_analyzer.analyse_kaufsignal_perioden(data, Auswertung_tage, min_veraenderung, klassifikation["Profil"], klassifikation["Trading_Status"])
            # macht es nicht Sinn, die folgende Formatierung in die Funktion mit aufzunehmen?
            df_details = pd.DataFrame(analyse_ergebnis["Perioden_Bewertung"])
            df_details.columns = ["Start", "Ende", "Signal", "Wert1", "Wert2", "Beschreibung", "ExtraInfo"]
            df_details["Signal"] = df_details["Signal"].astype(str).str.upper() == "TRUE"
            df_details["Start"] = pd.to_datetime(df_details["Start"])
            df_details["Ende"] = pd.to_datetime(df_details["Ende"])
            st.subheader("Kennzeichnung der Original-Perioden")
            period_analyzer.plot_priodenchart(data, name, 3, kaufperioden=df_details)
            """
        

# ------------------------------
# Sidebar: Parameter laden
# ------------------------------
def lade_sidebar_parameter():
    zeitraum = st.sidebar.selectbox("Zeitraum wählen", ["6 Monate", "1 Jahr", "3 Jahre"])
    period_map = {
        "6 Monate": 180,
        "1 Jahr": 365,
        "3 Jahre": 1095
    }
    tage = period_map[zeitraum]

    min_veraenderung = st.sidebar.slider(
        "📈 Mindestkursanstieg (%)",
        min_value=0.0,
        max_value=0.3,
        value=0.08,
        step=0.01
    )

    auswertung_tage = st.sidebar.slider(
        "📅 Auswertung-Tage für Performance-Auswertung",
        min_value=10,
        max_value=200,
        value=61,
        step=1
    )

    # --------------------------------------------------
    # ⚙️ MACD Parameter
    # --------------------------------------------------
    st.sidebar.subheader("⚙️ MACD Parameter")

    short_window = st.sidebar.number_input(
        "Short EMA Periode",
        min_value=5,
        max_value=50,
        value=12
    )

    long_window = st.sidebar.number_input(
        "Long EMA Periode",
        min_value=10,
        max_value=100,
        value=26
    )

    signal_window = st.sidebar.number_input(
        "Signal EMA Periode",
        min_value=5,
        max_value=30,
        value=9
    )

    return tage, min_veraenderung, auswertung_tage, short_window, long_window, signal_window

def zeige_kaufsignal_analyse(data, Auswertung_tage, min_veraenderung):
    """
    Führt die Analyse der Kaufsignal-Perioden durch
    und zeigt die wichtigsten Kennzahlen und Details in Streamlit an.
    """

    # Analyse aus Kernfunktion laden
    analyse_ergebnis = analyse_kaufsignal_perioden(data, Auswertung_tage, min_veraenderung)

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

def plot_priodenchart(data, symbol, version, kaufperioden=None):
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

def zeige_swingtrading_signalauswertung(data, service_result):

    trefferquote = service_result.get("trefferquote")

    perioden_bewertung = service_result.get("perioden_bewertung")
    

    if trefferquote is None:
        st.metric("Trefferquote", "–")
    else:
        st.metric("Trefferquote", f"{trefferquote:.2f} %")

    if perioden_bewertung is None or len(perioden_bewertung) == 0:
        st.info("Keine bewerteten Perioden vorhanden.")
    else:
        with st.expander("📘 Abgeschlossene Perioden"):
            st.dataframe(service_result["perioden_bewertung"])

    with st.expander("📊 Alle Signale"):
        st.dataframe(service_result["signals"])


# ---------------------------------------------------------
# Ergänzende Funktion für DailyMail
# ---------------------------------------------------------
def berechne_swingtrading_trefferquote(data, auswertung_tage, min_veraenderung):
    """
    Gibt nur die Trefferquote (prozent_true) zurück
    """

    analyse_ergebnis = analyse_kaufsignal_perioden(
        data,
        auswertung_tage,
        min_veraenderung
    )

    if "Perioden_Bewertung" not in analyse_ergebnis:
        return None

    df_details = pd.DataFrame(analyse_ergebnis["Perioden_Bewertung"])
    df_details.columns = [
        "Start", "Ende", "Signal",
        "Wert1", "Wert2", "Beschreibung", "ExtraInfo"
    ]

    df_details["Signal"] = df_details["Signal"].astype(str).str.upper() == "TRUE"
    df_details["Start"] = pd.to_datetime(df_details["Start"])
    df_details["Ende"] = pd.to_datetime(df_details["Ende"])

    letztes_datum = data.index[-1]
    df_details["Bewertung_fertig_ab"] = (
        df_details["Ende"] + pd.Timedelta(days=auswertung_tage)
    )

    df_abgeschlossen = df_details[
        df_details["Bewertung_fertig_ab"] <= letztes_datum
    ]

    gesamt = len(df_abgeschlossen)
    if gesamt == 0:
        return 0.0

    prozent_true = (df_abgeschlossen["Signal"].sum() / gesamt) * 100
    return round(prozent_true, 2)
