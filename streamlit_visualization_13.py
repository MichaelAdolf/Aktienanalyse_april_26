import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from io import BytesIO
import json
from pathlib import Path
from signals_generation import (
    FundamentalAnalysis,
    Analystenbewertung
)

from trading_v2.rule_engine import RuleEngineV2
from trading_v2.features import build_features
from trading_v2.telemetry import write_daily_log
from trading_v2.wfo_optimizer import (optimize_symbol_wfo, write_learned, write_report)
from trading_v2.config_loader import load_global, load_learned, load_ui_policy, resolve_params

from SwingtradingSignale import(
    RSIAnalysis,
    MACDAnalysis,
    ADXAnalysis,
    MAAnalysis,
    BollingerAnalysis,
    StochasticAnalysis
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
    erklaere_fundamentales_umfeld,
    lade_aktien_stimmung,
    klassifiziere_aktie,
    erklaere_kategorien,
    save_watchlist_json
)


# 🔥 TEMPORÄR – Cache hart invalidieren
st.cache_data.clear()
st.cache_resource.clear()

def go_to(page_name):
    st.session_state.page = page_name

def get_rule_engine(active_profile: str, use_auto: bool):
    eng = RuleEngineV2()
    # Profil in Engine-Konfig setzen (wirkt in resolve_params über global_cfg)
    eng.global_cfg["active_profile"] = active_profile
    # Auto-learned AUS -> learned dict leer machen (damit nichts gemerged wird)
    if not use_auto:
        eng.learned = {}
    return eng

def render_interp(interp: dict):
    """
    Rendert Interpretation (headline/meaning/status/level) rein als UI.
    Keine Logik, nur Darstellung.
    """
    if not isinstance(interp, dict):
        st.caption(str(interp))
        return

    level = interp.get("level", "caption")
    meaning = interp.get("meaning", "")

    if level == "warning":
        st.warning(meaning)
    elif level == "info":
        st.info(meaning)
    else:
        st.caption(meaning)

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
    
        col_button, _ = st.columns([5, 1])
    
        with col_button:
            if st.button(f"{name} ({symbol})", key=f"btn_{symbol}_{i}"):
                st.session_state.page = (name, symbol)


def aktienseite(): 
    name, symbol = st.session_state.page
    # ---------------------------------------------------------
    # Sidebar-Parameter laden
    # ---------------------------------------------------------  
    tage, min_veraenderung, Auswertung_tage, use_auto, profile = lade_sidebar_parameter()
    
    st.sidebar.subheader("🧠 Lernende Parameter")
    
    if st.sidebar.button(
        "Parameter für dieses Symbol rekalibrieren",
        help="Führt eine Walk-Forward-Optimierung der BUY-Parameter "
             "für das aktuell ausgewählte Symbol durch "
             "und speichert das Ergebnis in learned_params.json."
    ):
        with st.spinner(f"Rekalibriere Parameter für {symbol} ..."):
            from learning_optimizer import learn_symbol
    
            res = learn_symbol(
                symbol=symbol,
                period="4y",
                persist=True,
                write_json_report=True,
            )
    
        st.sidebar.success(
            f"✅ Neu gelernt für {res.symbol}\n"
            f"OOS-Hitrate: {res.best_oos_hit_rate:.2f}"
        )


    # für Home-Seite Ampel-Rendering merken
    st.session_state["active_profile"] = profile
    st.session_state["use_auto"] = use_auto
    
    # ---------------------------------------------------------
    # Laden aller Daten der letzten 4 jahre für weitere 
    # grundlegende Berechnungen und Anzeigen
    # ---------------------------------------------------------
    max_period = "4y"
    try:
        data_full = lade_daten_aktie(symbol, period=max_period)
        data_full = berechne_indikatoren(data_full)
        engine = get_rule_engine(profile, use_auto)
        decision_v2 = engine.evaluate(symbol, data_full)
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
    Analysten = Analystenbewertung()

    # ---------------------------------------------------------
    # Laden und Analysieren der Fundamentaldaten
    # ---------------------------------------------------------  
    fundamentaldaten = lade_fundamentaldaten(symbol)
    data_fund = fundamental_alanalyzer.fundamental_analyse(fundamentaldaten, symbol)
    sector = fundamentaldaten.get("sector")  # kann "Unknown" sein
    
    # global verfügbar machen
    global_cfg = load_global()
    global_cfg["active_profile"] = profile

    # ---------------------------------------------------------
    rsi_analysis = RSIAnalysis()
    macd_analysis = MACDAnalysis()
    ma_analysis = MAAnalysis()
    bollinger_analysis = BollingerAnalysis()
    stochastic_analysis = StochasticAnalysis()
    adx_analysis = ADXAnalysis()
    indikatoren_boards = indikatoren_databoards()
    indikatoren_diagram = indikatoren_plot()

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
    ma_result = ma_analysis.analyse(data)
    bollinger_result = bollinger_analysis.analyze(data)
    stochastic_result = stochastic_analysis.analyze(data)
    stoch_interp = stochastic_result["interpretation"]
    adx_result = adx_analysis.analyse(data)
    adx_interp = adx_result["interpretation"]
    
   
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
    tab_overview, tab_handel, tab_qualität, tab_charts, tab_fundamentals, tab_export, Algorithmus = st.tabs(
        ["📈 Übersicht", "🔔Handelsentscheidung", "🎯Algorithmus-Qualität", "📊 Charts", "🏦 Fundamentaldaten", "📤Export", "Algorithmus"]
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
                st.subheader("📌 Charakterisierung des Marktverhaltens")
                
                st.metric("Marktverhalten:", klassifikation["Profil"])
                st.metric("Handelsumfeld:", klassifikation["Trading_Status"])
                
                with st.expander("ℹ️ Erläuterung zum Marktverhalten"):
                    st.write(
                        erklaere_kategorien(
                            klassifikation["Profil"],
                            klassifikation["Trading_Status"]
                        )
                    )
                
                st.caption(
                    "Diese Einordnung beschreibt das typische Marktverhalten der Aktie "
                    "im betrachteten Zeitraum. Sie dient ausschließlich der Orientierung "
                    "und hat keinen Einfluss auf Handelssignale."
                )

        # --- 2️⃣ RECHTE SPALTE ---
        with col2:
            with st.container(border=True):
                st.subheader("Experteneinschätzung:")
                if summary_df is not None:
                    Analysten.zeichne_rating_gauge(rating_counts)

        # --- 2 Spalten Layout ---
        col1, col2 = st.columns([1,1])

        # --- 1️⃣ LINKE SPALTE ---
        with col1:
            with st.container(border=True):
                st.subheader("🏦 Fundamental Übersicht:")
                fundamental_alanalyzer.fundamental_summary(data_fund)
                with st.expander("ℹ️ Erläuterung zum fundamentalen Unternehmensumfeld"):
                    st.write(
                        erklaere_fundamentales_umfeld(data_fund)
                    )

        # --- 2️⃣ RECHTE SPALTE ---
        with col2:
            with st.container(border=True):
                st.subheader("🔄 Swingtrading Übersicht (RuleEngineV2)")
        
                if decision_v2.signal == "BUY":
                    st.success("✅ BUY – Entry Transition")
                elif decision_v2.signal == "SELL":
                    st.error("❌ SELL – Exit Transition")
                else:
                    st.info("⏸ HOLD – kein Trade")

        
        with st.container(border=True):
            st.subheader("📰 Marktstimmung (News)")
        
            sentiment = lade_aktien_stimmung(symbol, days=7, limit=12)
        
            s = sentiment.get("sentiment", "NEUTRAL")
            expl = sentiment.get("explanation", "")
            as_of = sentiment.get("as_of", "")
            contexts = sentiment.get("contexts", [])
        
            if s == "POSITIV":
                st.success(f"🟢 Positiv (Stand: {as_of})")
            elif s == "NEGATIV":
                st.error(f"🔴 Negativ (Stand: {as_of})")
            else:
                st.info(f"🟡 Neutral (Stand: {as_of})")
        
            st.caption(expl)
            st.caption("Hinweis: Rein informativ – hat keinen Einfluss auf Handelssignale.")
        
            if contexts:
                with st.expander("🧩 Kontext (automatisch erkannt)"):
                    st.write(", ".join(contexts))
        
            with st.expander("📄 Verwendete Schlagzeilen"):
                items = sentiment.get("headlines", [])
                if not items:
                    st.write("Keine Headlines verfügbar.")
                else:
                    for it in items:
                        title = it.get("title", "")
                        url = it.get("url", "")
                        src = it.get("source", "")
                        pub = it.get("published_at", "")
        
                        if url:
                            st.markdown(f"- [{title}]({url})  \n  <small>{src} · {pub}</small>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"- {title}  \n  <small>{src} · {pub}</small>", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # TAB HANDEL
    # ---------------------------------------------------------
    with tab_handel:
        with st.container(border=True):
                st.markdown("## 🧠 Handelsentscheidung (RuleEngineV2)")        
                with st.container(border=True):
                    if decision_v2.signal == "BUY":
                        st.success("✅ BUY – Einstiegssignal")
                    elif decision_v2.signal == "SELL":
                        st.error("❌ SELL – Ausstiegssignal")
                    else:
                        st.info("⏸ HOLD – keine Aktion")
        
                    st.markdown("### 🧠 Entscheidungsdetails")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Signal", decision_v2.signal)
                        st.metric("State", decision_v2.state)
                    
                    with col2:
                        st.metric("Confidence", f"{decision_v2.confidence:.2f}")

                    st.markdown("### ✅ Auslösende Regeln")
                    if decision_v2.reasons:
                        for r in decision_v2.reasons:
                            st.markdown(f"- ✔️ {r}")
                    else:
                        st.caption("Keine expliziten Regeln ausgelöst.")

                    with st.expander("🔍 Erweiterte Details (Regeln & Indikatoren)"):
                        if decision_v2.meta:
                            st.markdown("**Meta‑Informationen**")
                            st.json(decision_v2.meta)
                        st.markdown("**Aktive Entry‑Parameter**")
                        active_params = _load_rule_params(
                            symbol,
                            active_profile=profile,
                            use_auto=use_auto
                        )
                        st.json(active_params)
                        st.markdown("**Feature‑Snapshot (letzter Handelstag)**")
                        try:
                            feat = build_features(data)
                            st.json({
                                "RSI": round(feat.get("rsi", float("nan")), 2),
                                "MACD_Hist": round(feat.get("macd_hist", float("nan")), 4),
                                "BB_Position": round(feat.get("bb_pos", float("nan")), 3),
                                "ADX": round(feat.get("adx", float("nan")), 2),
                                "Close": round(feat.get("close", float("nan")), 2),
                            })
                        except Exception:
                            st.caption("Feature‑Snapshot aktuell nicht verfügbar.")
    
    # ---------------------------------------------------------
    # TAB Qualität
    # ---------------------------------------------------------
    with tab_qualität:
        with st.container(border=True):
            zeige_ruleengine_buyperioden_und_trefferquote(                
                data=data,
                symbol=symbol,
                Auswertung_tage=Auswertung_tage,
                min_veraenderung=min_veraenderung,
                max_gap_days=5,
                active_profile=profile,
                use_auto=use_auto
            )

        st.caption(
            f"Profil: **{profile}** | Auto(learned): **{'ON' if use_auto else 'OFF'}**"
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
                # --- Interaktive MA-Interpretation aus Analyse-Layer ---
                ma_analyser = MAAnalysis(short_window=10, long_window=50)
                ma_result = ma_analyser.analyse(data)
                ma_interp = ma_result.get("interpretation", {})
        
                st.markdown(f"### {ma_interp.get('headline', 'MA10/MA50')}")
                render_interp(ma_interp)
        
                # Optional: kleine Faktenbox für Einsteiger (rein informativ)
                st.caption(
                    f"MA10: {ma_result.get('ma_short')} | MA50: {ma_result.get('ma_long')} | "
                    f"Trend: {ma_result.get('ma_trend')} | Crossover: {ma_result.get('ma_cross')}"
                )

        with col2:
            with st.container(border=True):
                st.subheader("Bollinger Analyse")
                main_analyzer.plot_bollinger(name, 1)             
                boll_interp = bollinger_result.get("interpretation", {})
                if boll_interp:
                    st.markdown(f"### {boll_interp.get('headline','Bollinger')}")
                    render_interp(boll_interp)
                # Optional: kleine Faktenbox für Einsteiger (rein informativ)
                st.caption(
                    f"Volatilität (Bollinger Bandbreite): {bollinger_result['bandwidth']:.2f}"
                )

        col1, col2 = st.columns([1,1])
        # ---------------------------------------------------------
        # 1️⃣ LINKE SPALTE
        # ---------------------------------------------------------
        with col1:
            with st.container(border=True):
                indikatoren_boards.rsi_databoard(rsi_latest, rsi_history)
                indikatoren_diagram.plot_rsi(data, symbol)
                st.markdown(f"### RSI – {rsi_interp.get('headline', '')}")
                render_interp(rsi_interp)
        # ---------------------------------------------------------
        # 2️⃣ RECHTE SPALTE
        # ---------------------------------------------------------
        with col2:
            with st.container(border=True):
                # MACD Chart
                indikatoren_boards.macd_databoard(macd_result["hist"], macd_result["signal"], macd_result["macd"])
                #macd_analyzer.plot_macd(data, symbol)
                indikatoren_diagram.plot_macd(data, symbol)
                st.markdown(f"### MACD – {macd_interp.get('headline', '')}")
                render_interp(macd_interp)
                        
        col1, col2 = st.columns([1,1])
        # ---------------------------------------------------------
        # 1️⃣ LINKE SPALTE
        # ---------------------------------------------------------
        with col1:
            with st.container(border=True):
                # Stochastic Oscillator Chart
                st.subheader("Stochastics Analyse")
                indikatoren_diagram.plot_stoch(data, symbol)
                st.markdown(f"### Sochastics Analyse – {stoch_interp.get('headline', '')}")
                render_interp(stoch_interp)
        
        # ---------------------------------------------------------
        # 2️⃣ RECHTE SPALTE
        # ---------------------------------------------------------
        with col2:
            with st.container(border=True):
                st.subheader("ADX Analyse")
                indikatoren_diagram.plot_adx(data, symbol)
                st.markdown(f"### ADX Analyse – {adx_interp.get('headline', '')}")
                render_interp(adx_interp)

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
        
    with tab_export:
        st.subheader("📥 Export: RSI & Indikatoren (letzte 1,5 Jahre)")
    
        st.write(
            "Download einer Excel-Datei mit Daily-Werten für: Close, Bollinger (Upper/Lower/Middle), "
            "MA10/MA50, RSI, MACD (inkl. Signal & Histogramm), Stochastics (%K/%D) sowie ADX (+DI/-DI)."
        )
    
        # Excel erzeugen (Bytes) + DataFrame Vorschau + fehlende Spalten
        export_bytes, df_export, missing_cols, export_type = build_indicator_export_excel(data_full, symbol, years=1.5)

        # Optional: Hinweis auf fehlende Spalten
        if missing_cols:
            st.warning(
                "Hinweis: Einige Spalten fehlen in den Daten und wurden nicht exportiert: "
                + ", ".join(missing_cols)
            )
    
        # Download-Button
        if export_type == "xlsx":
            file_name = f"{symbol}_Indicators_Last_18M.xlsx"
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            file_name = f"{symbol}_Indicators_Last_18M.csv"
            mime = "text/csv"
        
        st.download_button(
            label="⬇️ Download (letzte 1,5 Jahre)",
            data=export_bytes,
            file_name=file_name,
            mime=mime
        )
    
        # Optional: kleine Vorschau
        with st.expander("🔎 Vorschau (erste 20 Zeilen)"):
            st.dataframe(df_export.head(20))
                
    
    with Algorithmus:
        st.subheader("🧪 Algorithmus (RuleEngineV2) – Aktive Parameter & Profilvergleich")
    
        # 1) Aktiver Zustand (was gerade ausgewählt ist)
        st.caption(
            f"Profil: **{profile}** | Auto(learned): **{'ON' if use_auto else 'OFF'}** "
            f"| Auswertung: {Auswertung_tage} Tage | Mindestanstieg: {min_veraenderung*100:.1f}%"
        )
    
        # 2) Aktive Entry-Parameter für das aktuell ausgewählte Profil (und Auto ON/OFF)
        st.markdown("### ✅ Aktive Entry-Parameter (für dieses Symbol)")
        active_params = _load_rule_params(symbol, active_profile=profile, use_auto=use_auto)
        st.json(active_params)
    
        # 3) Profilvergleich – immer live neu berechnen
        st.markdown("### 📊 Profilvergleich (Conservative vs Balanced vs Aggressive)")
    
        rows = []
        profiles = ["Conservative", "Balanced", "Aggressive"]
    
        for prof in profiles:
            p = _load_rule_params(symbol, active_profile=prof, use_auto=use_auto)
    
            buy_dates = _ruleengine_buy_days(
                data,
                rsi_thr=float(p.get("rsi_thr", 35)),
                bb_pos_thr=float(p.get("bb_pos_thr", 0.20)),
                require_hist_rising=bool(p.get("require_hist_rising", False)),
            )
    
            periods = _cluster_periods_from_dates(buy_dates, max_gap_days=5)
            df_eval = _evaluate_periods(periods, data, Auswertung_tage, min_veraenderung)
    
            if df_eval is None or df_eval.empty:
                done = 0
                open_ = 0
                hitrate = None
            else:
                df_done = df_eval[df_eval["Signal"].notna()].copy()
                df_open = df_eval[df_eval["Signal"].isna()].copy()
                done = len(df_done)
                open_ = len(df_open)
                hitrate = round(float(df_done["Signal"].mean() * 100), 2) if done > 0 else None
    
            rows.append({
                "Profil": prof,
                "rsi_thr": p.get("rsi_thr"),
                "bb_pos_thr": p.get("bb_pos_thr"),
                "require_hist_rising": p.get("require_hist_rising"),
                "BUY-Tage": len(buy_dates),
                "Perioden (gesamt)": len(periods),
                "Abgeschlossen": done,
                "Offen": open_,
                "Trefferquote % (abgeschlossen)": hitrate,
            })
    
        df_cmp = pd.DataFrame(rows)
    
        # Highlight / Sortierung (optional)
        df_cmp = df_cmp.sort_values(by=["BUY-Tage", "Trefferquote % (abgeschlossen)"], ascending=[False, False])
    
        st.dataframe(df_cmp, use_container_width=True)
    
        # 4) Optional: Detail-Expander pro Profil (Perioden-Tabelle)
        with st.expander("🔍 Details je Profil (Perioden-Tabelle)"):
            prof_pick = st.selectbox("Profil für Details", profiles, index=profiles.index(profile), key="algo_profile_details_pick")
            p = _load_rule_params(symbol, active_profile=prof_pick, use_auto=use_auto)
            buy_dates = _ruleengine_buy_days(
                data,
                rsi_thr=float(p.get("rsi_thr", 35)),
                bb_pos_thr=float(p.get("bb_pos_thr", 0.20)),
                require_hist_rising=bool(p.get("require_hist_rising", False)),
            )
            periods = _cluster_periods_from_dates(buy_dates, max_gap_days=5)
            df_eval = _evaluate_periods(periods, data, Auswertung_tage, min_veraenderung)
            if df_eval is None or df_eval.empty:
                st.info("Keine Perioden im aktuellen Zeitraum.")
            else:
                st.dataframe(df_eval, use_container_width=True)
  

# ------------------------------
# Sidebar: Parameter laden
# ------------------------------
def lade_sidebar_parameter():
    zeitraum = st.sidebar.selectbox("Zeitraum wählen", ["6 Monate", "1 Jahr", "3 Jahre"], key="sidebar_time_period")
    period_map = {
        "6 Monate": 180,
        "1 Jahr": 365,
        "2 Jahre": 730,
        "3 Jahre": 1095
    }
    tage = period_map[zeitraum]

    min_veraenderung = st.sidebar.slider(
        "📈 Mindestkursanstieg (%)",
        min_value=0.0,
        max_value=0.3,
        value=0.08,
        step=0.01,
        key="sidebar_min_veraenderung"
    )

    auswertung_tage = st.sidebar.slider(
        "📅 Auswertung-Tage für Performance-Auswertung",
        min_value=10,
        max_value=200,
        value=61,
        step=1,
        key="sidebar_time_window"
    )

    use_auto = st.sidebar.toggle("Parameter: Auto (learned) verwenden", value=False, key="sidebar_use_auto_learned")
    st.sidebar.subheader("🧠 Strategie-Profil")
    profile = st.sidebar.selectbox(
        "Profil wählen",
        ["Conservative", "Balanced", "Aggressive"],
        index=0,
        key="sidebar_strategy_profile"
    )
    
    return tage, min_veraenderung, auswertung_tage, use_auto, profile

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

import json
from pathlib import Path


def _load_rule_params(symbol, active_profile, use_auto):
    global_cfg = load_global()
    policy = load_ui_policy()

    global_cfg["active_profile"] = active_profile
    learned = load_learned() if use_auto else {}

    return resolve_params(
        symbol=symbol,
        mode=policy.mode,
        global_cfg=global_cfg,
        learned=learned,
        active_profile=active_profile,
    )

def _ruleengine_buy_days(data: pd.DataFrame, rsi_thr: float, bb_pos_thr: float, require_hist_rising: bool):
    """
    Ermittelt BUY-Tage nach Entry-Regel:
    RSI <= rsi_thr
    UND (bb_pos <= bb_pos_thr ODER Close <= BB_Lower)
    UND MACD_Hist < 0
    UND optional hist_rising (MACD_Hist(t) > MACD_Hist(t-1))
    """
    buy_dates = []
    if data is None or data.empty:
        return buy_dates

    needed = ["Close", "BB_Upper", "BB_Lower", "RSI", "MACD_Hist"]
    for c in needed:
        if c not in data.columns:
            return buy_dates

    for i in range(1, len(data)):
        row = data.iloc[i]
        prev = data.iloc[i - 1]

        # NaN guard
        if pd.isna(row["Close"]) or pd.isna(row["BB_Upper"]) or pd.isna(row["BB_Lower"]) or pd.isna(row["RSI"]) or pd.isna(row["MACD_Hist"]):
            continue

        denom = float(row["BB_Upper"] - row["BB_Lower"])
        bb_pos = float((row["Close"] - row["BB_Lower"]) / denom) if denom != 0 else 0.5

        cond = (float(row["RSI"]) <= float(rsi_thr)) \
               and ((bb_pos <= float(bb_pos_thr)) or (float(row["Close"]) <= float(row["BB_Lower"]))) \
               and (float(row["MACD_Hist"]) < 0.0)

        if require_hist_rising:
            if pd.isna(prev["MACD_Hist"]):
                cond = False
            else:
                cond = cond and (float(row["MACD_Hist"]) > float(prev["MACD_Hist"]))

        if cond:
            buy_dates.append(data.index[i])

    return buy_dates


def _cluster_periods_from_dates(dates, max_gap_days: int = 5):
    """
    Cluster BUY-Dates zu Perioden:
    solange Abstand <= max_gap_days bleibt, gleiche Periode.
    Rückgabe: Liste (start, end)
    """
    if not dates:
        return []

    dates = sorted(dates)
    periods = []
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


def _evaluate_periods(periods, data: pd.DataFrame, Auswertung_tage: int, min_veraenderung: float):
    """
    Bewertet jede Periode ab END-Datum:
    - entry_price = Close am End-Datum
    - max_close in den nächsten Auswertung_tage
    - Signal True, wenn (max_close-entry)/entry >= min_veraenderung
    Offene Perioden (zu nah am Datenende) werden markiert und nicht in Trefferquote gerechnet.
    """
    rows = []
    if data is None or data.empty:
        return pd.DataFrame(rows)

    for (start, end) in periods:
        # End-Kurs finden
        if end not in data.index:
            continue

        end_idx = data.index.get_loc(end)
        entry_price = float(data["Close"].iloc[end_idx])

        lookahead_idx = end_idx + int(Auswertung_tage)
        if lookahead_idx >= len(data):
            # nicht auswertbar
            rows.append({
                "Start": start,
                "Ende": end,
                "Signal": None,
                "Start_Kurs": entry_price,
                "Max_Kurs": None,
                "Kurs_Diff": None,
                "Kommentar": "Periode noch nicht auswertbar (zu nah am Datenende)"
            })
            continue

        window = data["Close"].iloc[end_idx:lookahead_idx + 1]
        max_close = float(window.max())
        diff = (max_close - entry_price) / entry_price
        hit = diff >= float(min_veraenderung)

        rows.append({
            "Start": start,
            "Ende": end,
            "Signal": bool(hit),
            "Start_Kurs": round(entry_price, 4),
            "Max_Kurs": round(max_close, 4),
            "Kurs_Diff": round(diff, 4),
            "Kommentar": f"Max-Anstieg >= {min_veraenderung*100:.1f}%: {hit}"
        })

    return pd.DataFrame(rows)

def zeige_ruleengine_buyperioden_und_trefferquote(
    data: pd.DataFrame,
    symbol: str,
    Auswertung_tage: int,
    min_veraenderung: float,
    max_gap_days: int = 5,
    active_profile: str = "Conservative",
    use_auto: bool = True,
):
    """
    UI-Funktion:
    - erzeugt BUY-Dates nach Entry-Regeln
    - clustert Perioden (Gap<=5 Tage)
    - bewertet Perioden ab End-Datum (max Kurs in Auswertung_tage)
    - zeigt Trefferquote + Tabellen + optional Chart-Markierung (über plot_priodenchart)
    """
    params = _load_rule_params(symbol, active_profile=active_profile, use_auto=use_auto)
    buy_dates = _ruleengine_buy_days(
        data,
        rsi_thr=params["rsi_thr"],
        bb_pos_thr=params["bb_pos_thr"],
        require_hist_rising=params["require_hist_rising"]
    )

    st.subheader("🟦 RuleEngine-Entry (BUY) – Perioden & Trefferquote")
    st.caption(
        f"Profil: **{active_profile}** | Auto(learned): **{'ON' if use_auto else 'OFF'}**"
    )
    st.caption(
        f"Entry-Regeln: RSI≤{params['rsi_thr']}, bb_pos≤{params['bb_pos_thr']} (oder Close≤BB_Lower), MACD_Hist<0"
        + (", hist_rising erforderlich" if params["require_hist_rising"] else "")
        + f" | Perioden-Cluster: Gap≤{max_gap_days} Tage | Bewertung: {Auswertung_tage} Tage / Mindestanstieg {min_veraenderung*100:.1f}%"
    )

    if not buy_dates:
        st.warning("⚠️ Keine BUY-Tage nach Entry-Regeln im betrachteten Zeitraum gefunden.")
        # Diagnose: Wie oft erfüllt jede Bedingung alleine?
        _diagnose_entry_conditions(data, params["rsi_thr"], params["bb_pos_thr"], params["require_hist_rising"])
        return

    periods = _cluster_periods_from_dates(buy_dates, max_gap_days=max_gap_days)
    df_eval = _evaluate_periods(periods, data, Auswertung_tage, min_veraenderung)

    if df_eval.empty:
        st.info("Keine Perioden auswertbar.")
        return

    # Trefferquote nur über abgeschlossene Perioden (Signal != None)
    df_done = df_eval[df_eval["Signal"].notna()].copy()
    df_open = df_eval[df_eval["Signal"].isna()].copy()

    if len(df_done) > 0:
        hitrate = round(df_done["Signal"].mean() * 100, 2)
        st.metric("Trefferquote (nur abgeschlossene Perioden)", f"{hitrate} %")
        st.write(f"Abgeschlossene Perioden: {len(df_done)} | Offene Perioden: {len(df_open)}")
    else:
        st.metric("Trefferquote (nur abgeschlossene Perioden)", "–")
        st.write(f"Abgeschlossene Perioden: 0 | Offene Perioden: {len(df_open)}")

    with st.expander("📘 Perioden-Bewertung (Details)"):
        st.dataframe(df_eval)

    try:
        df_plot = df_eval.copy()
        df_plot["Start"] = pd.to_datetime(df_plot["Start"])
        df_plot["Ende"] = pd.to_datetime(df_plot["Ende"])
        # Signal None -> False für Plot (grau)
        df_plot["Signal"] = df_plot["Signal"].fillna(False).astype(bool)

        st.markdown("### 🗺️ Markierung der BUY-Perioden im Chart")
        plot_priodenchart(data, symbol, version=999, kaufperioden=df_plot[["Start", "Ende", "Signal"]])
    except Exception:
        pass


def _diagnose_entry_conditions(data: pd.DataFrame, rsi_thr: float, bb_pos_thr: float, require_hist_rising: bool):
    """
    Gibt dir eine Debug-Auswertung, warum 0 BUY-Tage entstehen:
    zählt wie viele Tage jede Bedingung erfüllt.
    """
    if data is None or data.empty:
        return
    needed = ["Close", "BB_Upper", "BB_Lower", "RSI", "MACD_Hist"]
    if any(c not in data.columns for c in needed):
        st.info("Diagnose nicht möglich: erforderliche Spalten fehlen.")
        return

    rsi_ok = 0
    bb_ok = 0
    hist_neg = 0
    hist_rise_ok = 0
    all_ok = 0

    for i in range(1, len(data)):
        row = data.iloc[i]
        prev = data.iloc[i - 1]
        if pd.isna(row["Close"]) or pd.isna(row["BB_Upper"]) or pd.isna(row["BB_Lower"]) or pd.isna(row["RSI"]) or pd.isna(row["MACD_Hist"]):
            continue

        denom = float(row["BB_Upper"] - row["BB_Lower"])
        bb_pos = float((row["Close"] - row["BB_Lower"]) / denom) if denom != 0 else 0.5

        c_rsi = float(row["RSI"]) <= float(rsi_thr)
        c_bb = (bb_pos <= float(bb_pos_thr)) or (float(row["Close"]) <= float(row["BB_Lower"]))
        c_hist = float(row["MACD_Hist"]) < 0.0
        c_rise = True
        if require_hist_rising:
            if pd.isna(prev["MACD_Hist"]):
                c_rise = False
            else:
                c_rise = float(row["MACD_Hist"]) > float(prev["MACD_Hist"])

        rsi_ok += int(c_rsi)
        bb_ok += int(c_bb)
        hist_neg += int(c_hist)
        hist_rise_ok += int(c_rise) if require_hist_rising else 0

        if c_rsi and c_bb and c_hist and (c_rise if require_hist_rising else True):
            all_ok += 1

    st.markdown("#### 🔎 Diagnose: Warum 0 BUY-Tage?")
    st.write(f"RSI≤{rsi_thr}: {rsi_ok} Tage")
    st.write(f"bb_pos≤{bb_pos_thr} oder Close≤BB_Lower: {bb_ok} Tage")
    st.write(f"MACD_Hist<0: {hist_neg} Tage")
    if require_hist_rising:
        st.write(f"hist_rising (Hist[t]>Hist[t-1]): {hist_rise_ok} Tage")
    st.write(f"ALLE Bedingungen zusammen: {all_ok} Tage")
        
# ---------------------------------------------------------
# Hilfsfunktion
# ---------------------------------------------------------

def build_indicator_export_excel(data_full: pd.DataFrame, symbol: str, years: float = 1.5) -> tuple[bytes, pd.DataFrame, list]:
    """
    Erzeugt eine Excel-Datei (Bytes) mit Daily-Indikatoren für die letzten 'years' Jahre.
    Rückgabe: (excel_bytes, df_export, missing_cols)
    """
    days = int(round(365 * years))  # 1.5 Jahre ≈ 547 Tage

    # Zeitzone robust übernehmen (yfinance index kann tz-aware oder tz-naive sein)
    tz = getattr(data_full.index, "tz", None)
    now = pd.Timestamp.now(tz=tz) if tz is not None else pd.Timestamp.now()
    start = now - pd.Timedelta(days=days)

    # Zeitraum filtern
    df = data_full.loc[data_full.index >= start].copy()

    # Spalten, die wir exportieren wollen (wie in berechne_indikatoren erzeugt)
    wanted_cols = [
        "Close",
        "BB_Upper", "BB_Lower", "BB_Middle",
        "MA10", "MA50",
        "RSI",
        "MACD", "MACD_Signal", "MACD_Hist",
        "Stoch_%K", "Stoch_%D",
        "ADX", "+DI", "-DI",
    ]

    # Fehlende Spalten erkennen (falls mal Indikatorberechnung nicht durchlief)
    missing = [c for c in wanted_cols if c not in df.columns]

    # Nur vorhandene Spalten exportieren (robust)
    export_cols = [c for c in wanted_cols if c in df.columns]
    df_export = df[export_cols].copy()

    # Datum als erste Spalte
    df_export = df_export.reset_index()
    date_col = df_export.columns[0]  # i.d.R. "Date" oder "index"
    df_export = df_export.rename(columns={date_col: "Datum"})

    
    # Excel erzeugen (wenn openpyxl verfügbar), sonst CSV-Fallback
    output = BytesIO()

    try:
        import openpyxl  # noqa: F401  (nur Verfügbarkeitscheck)

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            sheet = "Indicators_18M"
            df_export.to_excel(writer, index=False, sheet_name=sheet)

            # Optional: Spaltenbreite grob anpassen
            ws = writer.sheets[sheet]
            for col_idx, col_name in enumerate(df_export.columns, start=1):
                width = max(10, min(35, len(str(col_name)) + 2))
                col_letter = ws.cell(row=1, column=col_idx).column_letter
                ws.column_dimensions[col_letter].width = width

        output.seek(0)
        return output.getvalue(), df_export, missing, "xlsx"

    except Exception:
        # Fallback: CSV
        csv_bytes = df_export.to_csv(index=False).encode("utf-8")
        return csv_bytes, df_export, missing, "csv"
