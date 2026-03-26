import pandas as pd
import numpy as np
import streamlit as st

# ------------------------------------------------------------------
# Strategy Rules: definieren WIE aggressiv gehandelt wird
# ------------------------------------------------------------------

STRATEGY_RULES = {
    "Conservative": {
        "allowed_buy_types": ["trend_breakout"],
        "macd_mode": "strict",
        "allow_emerging_trend": False,
    },
    "Balanced": {
        "allowed_buy_types": ["trend_breakout", "trend_pullback"],
        "macd_mode": "normal",
        "allow_emerging_trend": True,
    },
    "Aggressive": {
        "allowed_buy_types": ["trend_breakout", "trend_pullback", "momentum_reentry"],
        "macd_mode": "loose",
        "allow_emerging_trend": True,
    },
}

# -------------------------------------------------
# Trader Decision Matrix: wie Profile Entscheidungen treffen
# -------------------------------------------------

TRADER_MATRIX = {
    "Conservative": {
        "allowed_situations": ["confirmed_trend"],
    },
    "Balanced": {
        "allowed_situations": ["confirmed_trend", "trend_pullback"],
    },
    "Aggressive": {
        "allowed_situations": ["confirmed_trend", "trend_pullback", "early_momentum"],
    },
}


def macd_allows_entry(macd, mode):
    if mode == "strict":
        return macd["bias"] == "bullish"

    if mode == "normal":
        return macd["histogram"] > 0

    if mode == "loose":
        return macd["histogram"] > -0.02 and macd["histogram_trend"] > 0

    return False


class RSIAnalysis:
    """
    Professionelle RSI-Regime-Analyse
    ---------------------------------
    Erkennt:
    - Marktregime (Bullish / Bearish / Sideways)
    - Überdehnung
    - Stärke der Aussage
    """

    def __init__(
        self,
        oversold: int = 30,
        overbought: int = 70,
        bullish_floor: int = 40,
        bearish_ceiling: int = 60
    ):
        self.oversold = oversold
        self.overbought = overbought
        self.bullish_floor = bullish_floor
        self.bearish_ceiling = bearish_ceiling

    def analyse(self, data: pd.DataFrame) -> dict:
        if "RSI" not in data.columns or len(data) < 2:
            return self._empty_result("RSI-Daten fehlen")

        rsi = float(data["RSI"].iloc[-1])
        prev_rsi = float(data["RSI"].iloc[-2])

        # -------------------------
        # Regime-Erkennung
        # -------------------------
        if rsi >= self.bullish_floor and prev_rsi >= self.bullish_floor:
            market_regime = "bullish"
        elif rsi <= self.bearish_ceiling and prev_rsi <= self.bearish_ceiling:
            market_regime = "bearish"
        else:
            market_regime = "sideways"

        # -------------------------
        # Überdehnung
        # -------------------------
        if rsi <= self.oversold:
            state = "oversold"
            bias = "mean_reversion_long"
            strength = min(1.0, (self.oversold - rsi) / self.oversold + 0.3)
            interpretation = {
                "headline": "Stark überverkauft",
                "meaning": "Der Kurs wurde stark verkauft und ist technisch überdehnt.",
                "chance": "Kurzfristige technische Erholung möglich.",
                "risk": "In starken Abwärtstrends kann der RSI lange überverkauft bleiben.",
                "typical_action": "Nur für kurzfristige Trades geeignet"
            }

        elif rsi >= self.overbought:
            state = "overbought"
            bias = "mean_reversion_short"
            strength = min(1.0, (rsi - self.overbought) / (100 - self.overbought) + 0.3)
            interpretation = {
                "headline": "Stark überkauft",
                "meaning": "Der Kurs ist kurzfristig stark gestiegen und technisch überdehnt.",
                "chance": "Rücksetzer oder Seitwärtsphase möglich.",
                "risk": "In starken Aufwärtstrends kann der RSI lange überkauft bleiben.",
                "typical_action": "Gewinne absichern oder Teilverkäufe prüfen"
            }

        else:
            if market_regime == "bullish" and rsi >= 55:
                state = "bullish_strength"
                bias = "trend_follow_long"
                strength = (rsi - 50) / 50
                interpretation = {
                    "headline": "Trendstärke im Aufwärtstrend",
                    "meaning": "Der RSI bestätigt einen stabilen Aufwärtstrend.",
                    "chance": "Trendfortsetzung wahrscheinlich.",
                    "risk": "Überhitzung bei sehr schnellem Anstieg möglich.",
                    "typical_action": "Trendfolge – Rücksetzer abwarten"
                }

            elif market_regime == "bearish" and rsi <= 45:
                state = "bearish_weakness"
                bias = "trend_follow_short"
                strength = (50 - rsi) / 50
                interpretation = {
                    "headline": "Abwärtsdruck bestätigt",
                    "meaning": "Der RSI bestätigt einen schwachen Markt.",
                    "chance": "Weitere Abgaben möglich.",
                    "risk": "Plötzliche Gegenbewegungen möglich.",
                    "typical_action": "Short-orientiert oder abwarten"
                }

            else:
                state = "neutral"
                bias = "none"
                strength = 0.0
                interpretation = {
                    "headline": "Neutral",
                    "meaning": "Der RSI zeigt aktuell keine klare Richtung.",
                    "chance": "Ausbruch aus der Range möglich.",
                    "risk": "Fehlsignale bei Seitwärtsmarkt.",
                    "typical_action": "Bestätigung durch andere Indikatoren abwarten"
                }

        return {
            "value": round(rsi, 2),
            "regime": market_regime,
            "state": state,
            "bias": bias,
            "strength": round(float(strength), 2),
            "interpretation": interpretation
        }
    
    def analyze_history(self, data):
        result = {
            "oversold_pct": round((data["RSI"] < self.oversold).mean() * 100, 1),
            "overbought_pct": round((data["RSI"] > self.overbought).mean() * 100, 1),
            "avg_rsi": round(data["RSI"].mean(), 2),
            "min_rsi": round(data["RSI"].min(), 2),
            "max_rsi": round(data["RSI"].max(), 2),
        }
        self.oversold_prozent = result["oversold_pct"]
        self.overbought_prozent = result["overbought_pct"]
        return result

    @staticmethod
    def _empty_result(reason: str) -> dict:
        return {
            "value": None,
            "regime": "unknown",
            "state": "invalid",
            "bias": "none",
            "strength": 0.0,
            "interpretation": reason
        }
    
    """
    rsi_analyser = RSIAnalysis()
    rsi_result = rsi_analyser.analyse(data)

    st.metric("RSI", rsi_result["value"])
    st.write(rsi_result["interpretation"])
    st.progress(rsi_result["strength"])
    """

class MACDAnalysis:
    """
    Professionelle MACD-Regime-Analyse
    ----------------------------------
    Erkennt:
    - Trendrichtung
    - Momentum
    - Übergangsphasen (Reversal / Weakening)
    """

    def __init__(
        self,
        min_hist_strength: float = 0.05
    ):
        self.min_hist_strength = min_hist_strength

    def analyse(self, data: pd.DataFrame) -> dict:
        required = {"MACD", "MACD_Signal", "MACD_Hist"}
        if not required.issubset(data.columns) or len(data) < 3:
            return self._empty_result("MACD-Daten fehlen")

        macd = float(data["MACD"].iloc[-1])
        signal = float(data["MACD_Signal"].iloc[-1])
        hist = float(data["MACD_Hist"].iloc[-1])

        prev_hist = float(data["MACD_Hist"].iloc[-2])
        prev_macd = float(data["MACD"].iloc[-2])

        # -------------------------
        # Grundregime (Trendrichtung)
        # -------------------------
        if macd > signal:
            regime = "bullish"
        elif macd < signal:
            regime = "bearish"
        else:
            regime = "neutral"

        # -------------------------
        # Momentum-Bewertung
        # -------------------------
        hist_trend = hist - prev_hist
        macd_trend = macd - prev_macd

        # -------------------------
        # Zustände
        # -------------------------
        if regime == "bullish":
            if hist > self.min_hist_strength and hist_trend > 0:
                state = "bullish_expansion"
                bias = "trend_follow_long"
                strength = min(1.0, abs(hist) * 5)
                interpretation = {
                    "headline": "Aufwärtstrend beschleunigt sich",
                    "meaning": "Der Markt befindet sich in einem Aufwärtstrend und das Momentum nimmt weiter zu.",
                    "chance": "Trendfortsetzung mit steigender Dynamik wahrscheinlich.",
                    "risk": "Späte Einstiege können zu Rücksetzern führen.",
                    "typical_action": "Trendfolge – Rücksetzer für Einstieg abwarten"
                }

            elif hist_trend < 0:
                state = "bullish_weakening"
                bias = "caution_long"
                strength = min(1.0, abs(hist_trend) * 3)
                interpretation = {
                    "headline": "Aufwärtstrend verliert Momentum",
                    "meaning": "Der übergeordnete Trend ist positiv, aber die Dynamik lässt nach.",
                    "chance": "Seitwärtsphase oder kurze Konsolidierung möglich.",
                    "risk": "Trend kann kippen, wenn Momentum weiter abnimmt.",
                    "typical_action": "Long-Positionen absichern oder Teilgewinne mitnehmen"
                }

            else:
                state = "bullish_neutral"
                bias = "trend_follow_long"
                strength = 0.2
                interpretation = {
                    "headline": "Stabiler Aufwärtstrend",
                    "meaning": "Der Markt steigt, aber ohne zusätzliche Beschleunigung.",
                    "chance": "Solide Trendfortsetzung möglich.",
                    "risk": "Fehlende Dynamik kann zu Seitwärtsbewegung führen.",
                    "typical_action": "Trend halten – auf Momentum-Zunahme achten"
                }

        elif regime == "bearish":
            if hist < -self.min_hist_strength and hist_trend < 0:
                state = "bearish_expansion"
                bias = "trend_follow_short"
                strength = min(1.0, abs(hist) * 5)
                interpretation = {
                    "headline": "Abwärtstrend verstärkt sich",
                    "meaning": "Der Markt befindet sich in einem klaren Abwärtstrend mit zunehmendem Verkaufsdruck.",
                    "chance": "Weitere Kursverluste wahrscheinlich.",
                    "risk": "Technische Gegenbewegungen können abrupt auftreten.",
                    "typical_action": "Short-Trades bevorzugen oder Longs meiden"
                }

            elif hist_trend > 0:
                state = "bearish_weakening"
                bias = "caution_short"
                strength = min(1.0, abs(hist_trend) * 3)
                interpretation = {
                    "headline": "Abwärtsdruck lässt nach",
                    "meaning": "Der Abwärtstrend verliert an Dynamik.",
                    "chance": "Erholung oder Seitwärtsphase möglich.",
                    "risk": "Trend kann nach kurzer Pause weiterlaufen.",
                    "typical_action": "Short-Gewinne sichern – Bestätigung abwarten"
                }

            else:
                state = "bearish_neutral"
                bias = "trend_follow_short"
                strength = 0.2
                interpretation = {
                    "headline": "Stabiler Abwärtstrend",
                    "meaning": "Der Markt fällt gleichmäßig ohne zusätzliche Beschleunigung.",
                    "chance": "Weiterer Abwärtsverlauf wahrscheinlich.",
                    "risk": "Plötzliche Gegenbewegungen möglich.",
                    "typical_action": "Short-orientiert bleiben, Stops beachten"
                }

        else:
            state = "transition"
            bias = "wait"
            strength = 0.0
            interpretation = {
                "headline": "Trendwechselphase",
                "meaning": "Der MACD zeigt aktuell keine klare Trendrichtung.",
                "chance": "Neuer Trend kann sich entwickeln.",
                "risk": "Erhöhte Fehlsignale in Übergangsphasen.",
                "typical_action": "Abwarten und andere Indikatoren nutzen"
            }

        return {
            "macd": round(macd, 4),
            "signal": round(signal, 4),
            "histogram": round(hist, 4),
            "regime": regime,
            "state": state,
            "bias": bias,
            "strength": round(float(strength), 2),
            "interpretation": interpretation
        }


    @staticmethod
    def _empty_result(reason: str) -> dict:
        return {
            "macd": None,
            "signal": None,
            "histogram": None,
            "regime": "unknown",
            "state": "invalid",
            "bias": "none",
            "strength": 0.0,
            "interpretation": reason
        }

class MACDAnalysis_Confirmations:
    """
    Erweiterte MACD-Analyse für Signal-Confirmations
    ------------------------------------------------
    Erkennt:
    - Trendrichtung (bullish / bearish / neutral)
    - Momentum & Stärke
    - Übergangsphasen (Weakening / Expansion)
    - Flattening / Plateau für frühe Wendepunkte
    """

    def __init__(self, min_hist_strength: float = 0.05, flatten_lookback: int = 5):
        self.min_hist_strength = min_hist_strength
        self.flatten_lookback = flatten_lookback  # Anzahl der Balken zur Flatten-Erkennung

    def analyse(self, data: pd.DataFrame) -> dict:
        required = {"MACD", "MACD_Signal", "MACD_Hist"}
        if not required.issubset(data.columns) or len(data) < self.flatten_lookback + 1:
            return self._empty_result("MACD-Daten fehlen")

        macd = float(data["MACD"].iloc[-1])
        signal = float(data["MACD_Signal"].iloc[-1])
        hist = float(data["MACD_Hist"].iloc[-1])

        prev_hist = float(data["MACD_Hist"].iloc[-2])
        prev_macd = float(data["MACD"].iloc[-2])

        # -------------------------
        # Grundregime (Trendrichtung)
        # -------------------------
        if macd > signal:
            regime = "bullish"
        elif macd < signal:
            regime = "bearish"
        else:
            regime = "neutral"

        # -------------------------
        # Momentum-Bewertung
        # -------------------------
        hist_trend = hist - prev_hist
        macd_trend = macd - prev_macd

        # -------------------------
        # Flattening / Plateau Detection
        # -------------------------
        recent_hist = data["MACD_Hist"].iloc[-self.flatten_lookback:]
        delta_hist = recent_hist.diff().abs().mean()  # mittlere absolute Differenz

        if abs(hist) < self.min_hist_strength and delta_hist < self.min_hist_strength / 2:
            flattening_signal = True
        else:
            flattening_signal = False

        # -------------------------
        # Zustände
        # -------------------------
        if regime == "bullish":
            if hist > self.min_hist_strength and hist_trend > 0:
                state = "bullish_expansion"
                bias = "trend_follow_long"
                strength = min(1.0, abs(hist) * 5)
                trend_signal = +1
            elif hist_trend < 0:
                state = "bullish_weakening"
                bias = "caution_long"
                strength = min(1.0, abs(hist_trend) * 3)
                trend_signal = +0.5
            else:
                state = "bullish_neutral"
                bias = "trend_follow_long"
                strength = 0.2
                trend_signal = +0.3

        elif regime == "bearish":
            if hist < -self.min_hist_strength and hist_trend < 0:
                state = "bearish_expansion"
                bias = "trend_follow_short"
                strength = min(1.0, abs(hist) * 5)
                trend_signal = -1
            elif hist_trend > 0:
                state = "bearish_weakening"
                bias = "caution_short"
                strength = min(1.0, abs(hist_trend) * 3)
                trend_signal = -0.5
            else:
                state = "bearish_neutral"
                bias = "trend_follow_short"
                strength = 0.2
                trend_signal = -0.3

        else:
            state = "transition"
            bias = "wait"
            strength = 0.0
            trend_signal = 0

        # -------------------------
        # Interpretation & Chancen/Risiken
        # -------------------------
        interpretation = {
            "headline": f"{state} erkannt",
            "meaning": "MACD-Analyse liefert Trendrichtung und Momentum.",
            "chance": "Trendfortsetzung oder Trendwende möglich.",
            "risk": "Falsche Signale bei plötzlicher Volatilität.",
            "typical_action": "Mit Bestätigung durch RSI, ADX, Bollinger, Stochastics handeln"
        }

        if flattening_signal:
            interpretation["headline"] += " + Flattening"
            interpretation["chance"] += " Frühzeitige Wendepunkte erkennbar."
            interpretation["risk"] += " Signal kann noch fehlsignalisieren."
            interpretation["typical_action"] += " Frühwarnung beachten, weitere Indikatoren prüfen."

        return {
            "macd": round(macd, 4),
            "signal": round(signal, 4),
            "histogram": round(hist, 4),
            "regime": regime,
            "state": state,
            "bias": bias,
            "strength": round(float(strength), 2),
            "trend_signal": trend_signal,
            "flattening_signal": flattening_signal,
            "interpretation": interpretation
        }

    @staticmethod
    def _empty_result(reason: str) -> dict:
        return {
            "macd": None,
            "signal": None,
            "histogram": None,
            "regime": "unknown",
            "state": "invalid",
            "bias": "none",
            "strength": 0.0,
            "trend_signal": 0,
            "flattening_signal": False,
            "interpretation": reason
        }

class ADXAnalysis:
    """
    ADX Regime Analyse
    ------------------
    Erkennt:
    - Trendstärke
    - Trendrichtung (nur wenn valide)
    - Trading-Umfeld (Trend vs. Range)
    """

    def __init__(
        self,
        weak_trend: float = 20,
        strong_trend: float = 25,
        extreme_trend: float = 40
    ):
        self.weak_trend = weak_trend
        self.strong_trend = strong_trend
        self.extreme_trend = extreme_trend

    def analyse(self, data: pd.DataFrame) -> dict:
        required = {"ADX", "+DI", "-DI"}
        if not required.issubset(data.columns) or len(data) < 2:
            return self._empty_result("ADX-Daten fehlen")

        adx = float(data["ADX"].iloc[-1])
        pdi = float(data["+DI"].iloc[-1])
        mdi = float(data["-DI"].iloc[-1])

        prev_adx = float(data["ADX"].iloc[-2])
        adx_trend = adx - prev_adx

        # -------------------------
        # Trendrichtung (nur sekundär!)
        # -------------------------
        if pdi > mdi:
            direction = "bullish"
        elif mdi > pdi:
            direction = "bearish"
        else:
            direction = "neutral"

        # -------------------------
        # Regime & State
        # -------------------------
        if adx < self.weak_trend:
            regime = "range"
            state = "no_trend"
            bias = "mean_reversion"
            strength = 0.0
            summary = "Seitwärtsmarkt"
            interpretation_short = "Kein klarer Trend – Trendstrategien meiden"
            interpretation_long = (
                "Der ADX liegt unterhalb der Trend-Schwelle. "
                "Der Markt bewegt sich überwiegend seitwärts. "
                "Trendfolgestrategien sind in solchen Phasen meist ineffektiv, "
                "während kurzfristige Gegenbewegungen häufiger auftreten."
            )
            chance = "Kurzfristige Gegenbewegungen bieten Trading-Gelegenheiten."
            risk = "Trendfolgestrategien sind ineffektiv, Risiko von Fehlsignalen."
            action_hint = "Abwarten / Range-Strategien"
        elif self.weak_trend <= adx < self.strong_trend:
            regime = "emerging_trend"
            state = f"{direction}_emerging"
            bias = "wait_for_confirmation"
            strength = (adx - self.weak_trend) / (self.strong_trend - self.weak_trend)
            summary = "Trend im Aufbau"
            interpretation_short = "Möglicher Trend – noch unbestätigt"
            interpretation_long = (
                "Der ADX steigt, hat aber noch keinen stabilen Trendbereich erreicht. "
                "Das deutet auf einen entstehenden Trend hin, der sich jedoch noch "
                "als Fehlsignal entpuppen kann."
            )
            chance = "Trend entsteht, mögliche frühe Einstiege."
            risk = "Trend ist noch unsicher, Fehlsignale möglich."
            action_hint = "Beobachten"

        elif self.strong_trend <= adx < self.extreme_trend:
            regime = "strong_trend"
            state = f"{direction}_trend"
            bias = f"trend_follow_{direction}"
            strength = min(1.0, adx / self.extreme_trend)
            summary = "Starker Trend"
            interpretation_short = "Stabiler Trend – gute Trendfolge"
            interpretation_long = (
                "Der ADX signalisiert einen klaren und stabilen Trend. "
                "In solchen Marktphasen haben Trendfolgestrategien eine erhöhte "
                "Erfolgswahrscheinlichkeit, da sich Bewegungen oft fortsetzen."
            )
            chance = "Klare Trendrichtung, Trendfolgestrategien erfolgversprechend."
            risk = "Markt kann plötzliche Gegenbewegungen zeigen."
            action_hint = "Trend handeln"

        else:
            regime = "extreme_trend"
            state = f"{direction}_exhaustion"
            bias = "risk_of_reversal"
            strength = 1.0
            summary = "Überdehnter Trend"
            interpretation_short = "Sehr starker Trend – Rücksetzer möglich"
            interpretation_long = (
                "Der ADX liegt auf extrem hohem Niveau. "
                "Solche Phasen gehen häufig mit einer Überdehnung einher. "
                "Neueinstiege bergen ein erhöhtes Risiko für plötzliche Rücksetzer "
                "oder Trendwenden."
            )
            chance = "Trend hat viel Kraft, Gewinnmitnahmen können sinnvoll sein."
            risk = "Hohe Gefahr von Trendwende oder plötzlichen Rücksetzern."
            action_hint = "Gewinne sichern / Vorsicht"

        # -------------------------
        # Trendbeschleunigung
        # -------------------------
        if adx_trend > 0:
            trend_acceleration = " Trend nimmt an Stärke zu"
        elif adx_trend < 0:
            trend_acceleration = " Trend verliert an Stärke"

        return {
            "adx": round(adx, 2),
            "pdi": round(pdi, 2),
            "mdi": round(mdi, 2),
            "regime": regime,
            "state": state,
            "bias": bias,
            "strength": round(float(strength), 2),
            "summary": summary,
            "interpretation_short": interpretation_short,
            "trend_acceleration": trend_acceleration,
            "interpretation_long": interpretation_long,
            "chance": chance,
            "risk": risk,
            "action_hint": action_hint
        }

    @staticmethod
    def _empty_result(reason: str) -> dict:
        return {
            "adx": None,
            "pdi": None,
            "mdi": None,
            "regime": "unknown",
            "state": "invalid",
            "bias": "none",
            "strength": 0.0,
            "interpretation": reason
        }
    
class MAAnalysis:
    """
    Analyse der gleitenden Durchschnitte (Moving Averages)
    ------------------------------------------------------
    Erkennt:
    - Kurz- vs. mittelfristiger Trend (MA10 vs. MA50)
    - Crossovers (bullish / bearish)
    - Trendstärke anhand Abstand MA10 ↔ MA50
    - Optional: Volatilität/ATR zur Anpassung der Signalstärke
    """

    def __init__(self, short_window: int = 10, long_window: int = 50):
        self.short_window = short_window
        self.long_window = long_window

    def analyse(self, data: pd.DataFrame) -> dict:
        required = {"Close"}
        if not required.issubset(data.columns) or len(data) < self.long_window:
            return self._empty_result("Nicht genügend Daten für MA-Analyse")

        close = data["Close"]

        # -------------------------
        # MA-Berechnung
        # -------------------------
        ma_short = close.rolling(self.short_window).mean()
        ma_long = close.rolling(self.long_window).mean()

        ma10 = ma_short.iloc[-1]
        ma50 = ma_long.iloc[-1]
        prev_ma10 = ma_short.iloc[-2]
        prev_ma50 = ma_long.iloc[-2]

        # -------------------------
        # Trendrichtung
        # -------------------------
        if ma10 > ma50:
            ma_trend = "bullish"
        elif ma10 < ma50:
            ma_trend = "bearish"
        else:
            ma_trend = "neutral"

        # -------------------------
        # Crossover
        # -------------------------
        if prev_ma10 < prev_ma50 and ma10 > ma50:
            ma_cross = "bullish_cross"
        elif prev_ma10 > prev_ma50 and ma10 < ma50:
            ma_cross = "bearish_cross"
        else:
            ma_cross = "none"

        # -------------------------
        # Trendstärke (Abstand)
        # -------------------------
        distance = ma10 - ma50
        relative_distance = distance / ma50 if ma50 != 0 else 0.0
        strength = min(1.0, abs(relative_distance) * 5)  # Normierung 0-1

        # -------------------------
        # Optional: ATR / Volatilität
        # -------------------------
        if {"High", "Low", "Close"}.issubset(data.columns):
            high = data["High"]
            low = data["Low"]
            close_prev = close.shift(1)
            tr = pd.concat([
                high - low,
                (high - close_prev).abs(),
                (low - close_prev).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(self.long_window).mean().iloc[-1]
        else:
            atr = None

        # -------------------------
        # Interpretation
        # -------------------------
        interpretation = {
            "headline": "MA-Analyse",
            "meaning": f"MA{self.short_window} vs. MA{self.long_window} zeigt {ma_trend} Trend.",
            "chance": "Trendrichtung kann für Entries genutzt werden.",
            "risk": "Kurzfristige Crossovers können Fehlsignale sein.",
            "typical_action": "MA-Trend als Bestätigung oder Filter nutzen"
        }

        return {
            "ma_short": round(ma10, 4),
            "ma_long": round(ma50, 4),
            "ma_trend": ma_trend,
            "ma_cross": ma_cross,
            "distance": round(distance, 4),
            "strength": round(strength, 2),
            "atr": round(atr, 4) if atr is not None else None,
            "interpretation": interpretation
        }

    @staticmethod
    def _empty_result(reason: str) -> dict:
        return {
            "ma_short": None,
            "ma_long": None,
            "ma_trend": "unknown",
            "ma_cross": "none",
            "distance": 0.0,
            "strength": 0.0,
            "atr": None,
            "interpretation": reason
        }
    
class BollingerAnalysis:
    def analyze(self, data):
        last = data.iloc[-1]

        close = last["Close"]
        upper = last["BB_Upper"]
        lower = last["BB_Lower"]
        mid = last["BB_Middle"]

        width = (upper - lower) / mid

        if close <= lower:
            state = "Below_Lower"
            score = +1
            summary = "Preis am unteren Band"
            interpretation_short = "Preis liegt am unteren Band"
            interpretation_long = (
                "Der Kurs notiert am unteren Bollinger-Band, was auf eine starke Unterbewertung "
                "und erhöhte Volatilität hinweist. Dies kann eine attraktive Einstiegszone für Long-Positionen darstellen, "
                "jedoch besteht das Risiko weiterer Abwärtsbewegungen."
            )
            action_hint = "Mögliches Kaufsignal – Risiko beachten"
            chance = "Attraktiver Einstiegszeitpunkt bei potenzieller Bodenbildung."
            risk = "Markt könnte weiter fallen, trotz Überverkauftheit."

        elif close < mid:
            state = "Lower_Half"
            score = +0.5
            state = "Lower_Half"
            score = +0.5
            summary = "Preis in der unteren Hälfte"
            interpretation_short = "Preis in der unteren Hälfte"
            interpretation_long = (
                "Der Kurs bewegt sich in der unteren Hälfte der Bollinger-Bänder, was auf eine potenziell "
                "günstige Long-Position hinweist. Die Volatilität ist moderat, und der Markt zeigt keine extremen Bewegungen."
            )
            action_hint = "Long-Position möglich, Trend beobachten"
            chance = "Preis in günstiger Zone, moderates Aufwärtspotenzial."
            risk = "Trend könnte seitwärts oder schwach bleiben."

        elif close > upper:
            state = "Above_Upper"
            score = -1
            summary = "Preis über dem oberen Band"
            interpretation_short = "Preis über dem oberen Band"
            interpretation_long = (
                "Der Kurs notiert oberhalb des oberen Bollinger-Bandes und gilt als überdehnt. "
                "Dies weist auf eine mögliche technische Gegenreaktion hin, und es besteht ein erhöhtes Risiko für Rücksetzer."
            )
            action_hint = "Vorsicht bei Neueinstiegen – Gewinnmitnahmen erwägen"
            chance = "Starke Aufwärtsdynamik vorhanden."
            risk = "Hohe Wahrscheinlichkeit für technische Gegenreaktion."

        else:
            state = "Neutral"
            score = 0
            summary = "Preis nahe Mittelband"
            interpretation_short = "Preis nahe Mittelband"
            interpretation_long = (
                "Der Kurs befindet sich nahe dem mittleren Bollinger-Band, was auf eine stabile Marktphase "
                "ohne ausgeprägte Über- oder Unterbewertung hindeutet."
            )
            action_hint = "Abwarten oder Seitwärtsstrategie nutzen"
            chance = "Markt zeigt Stabilität ohne Extreme."
            risk = "Keine klaren Signale, mögliche Seitwärtsbewegung."

        return {
            "state": state,
            "score": score,
            "bandwidth": round(width, 3),
            "interpretation_short": interpretation_short,
            "summary": summary,
            "interpretation_long": interpretation_long,
            "action_hint": action_hint,
            "chance": chance,
            "risk": risk
        }

class StochasticAnalysis:
    def analyze(self, data):
        last = data.iloc[-1]
        prev = data.iloc[-2]

        k = last["Stoch_%K"]
        d = last["Stoch_%D"]

        bullish_cross = prev["Stoch_%K"] < prev["Stoch_%D"] and k > d
        bearish_cross = prev["Stoch_%K"] > prev["Stoch_%D"] and k < d

        if k < 20 and bullish_cross:
            regime = "Oversold_Reversal"
            score = +1
            summary = "Überverkauftes bullishes Signal"
            interpretation_short = "Überverkauft und günstiges Kaufsignal"
            interpretation_long = (
                "Der Stochastic-Oszillator zeigt eine Überverkauft-Situation zusammen mit "
                "einem bullischen Kreuz (K % über D %). Das kann eine gute Gelegenheit für eine technische "
                "Gegenbewegung oder Trendwende sein."
            )
            action_hint = "Long-Position erwägen, Stop-Loss setzen"
            chance = "Hohe Wahrscheinlichkeit für Erholung oder Trendwende."
            risk = "Signal kann in starkem Abwärtstrend versagen, weitere Bestätigung nötig."

        elif k > 80 and bearish_cross:
            regime = "Overbought_Reversal"
            score = -1
            summary = "Überkauftes bearishes Signal"
            interpretation_short = "Überkauft mit Verkaufsignal"
            interpretation_long = (
                "Der Indikator signalisiert eine Überkauft-Situation mit einem bearischen Kreuz. "
                "Das weist auf eine mögliche Trendwende nach unten oder einen Rücksetzer hin."
            )
            action_hint = "Gewinne sichern, Short-Position prüfen"
            chance = "Potenzial für kurzfristige Korrektur oder Trendwende."
            risk = "Signal könnte ein Fehlausbruch sein, Trend könnte anhalten."

        elif k > d and k < 80:
            regime = "Bullish_Momentum"
            score = +0.5
            summary = "Positives Momentum"
            interpretation_short = "Bullishes Momentum, aber nicht überkauft"
            interpretation_long = (
                "Der Stochastic zeigt, dass das Momentum auf der Long-Seite liegt, "
                "jedoch ohne extreme Überkauft-Signale. Eine moderate Aufwärtsbewegung ist wahrscheinlich."
            )
            action_hint = "Positionen halten oder ausbauen"
            chance = "Fortsetzung des Aufwärtstrends mit moderatem Risiko."
            risk = "Markt kann kurzfristig konsolidieren oder korrigieren."

        elif k < d and k > 20:
            regime = "Bearish_Momentum"
            score = -0.5
            summary = "Negatives Momentum"
            interpretation_short = "Bearishes Momentum ohne Überverkauft"
            interpretation_long = (
                "Das Momentum liegt auf der Short-Seite, aber ohne eine ausgeprägte Überverkauft-Situation. "
                "Der Trend könnte sich abschwächen oder eine Korrektur einleiten."
            )
            action_hint = "Vorsicht walten lassen, Stopp beachten"
            chance = "Möglichkeit für Trendwende oder kurzfristige Erholung."
            risk = "Abschwächung könnte nur eine Pause sein, Abwärtstrend bleibt intakt."

        else:
            regime = "Neutral"
            score = 0
            summary = "Kein klares Timing"
            interpretation_short = "Neutraler Zustand"
            interpretation_long = (
                "Der Stochastic-Indikator liefert derzeit keine klaren Signale für eine Trendwende oder ein "
                "starkes Momentum. Marktbewegungen sind eher unentschlossen."
            )
            action_hint = "Abwarten und Markt beobachten"
            chance = "Markt könnte sich bald entscheiden, gute Einstiegsgelegenheiten möglich."
            risk = "Unklare Marktphase birgt Unsicherheit und erhöhtes Risiko."

        return {
            "regime": regime,
            "score": score,
            "k": round(k, 2),
            "d": round(d, 2),
            "summary": summary,
            "interpretation_short": interpretation_short,
            "interpretation_long": interpretation_long,
            "action_hint": action_hint,
            "chance": chance,
            "risk": risk
        }

class ATRQualityAnalysis:
    """
    Bewertet die Einstiegsqualität anhand der ATR (Average True Range)
    und der aktuellen Kursposition innerhalb der typischen Volatilität.
    """

    def __init__(self, atr_multiplier: float = 1.0):
        """
        :param atr_multiplier: Faktor, der die Sensitivität bestimmt. 
                               Höher = vorsichtiger bei hoher Volatilität.
        """
        self.atr_multiplier = atr_multiplier
    
    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        Berechnet den Average True Range (ATR) und hängt ihn an den DataFrame an.
        """
        data = data.copy()
        high = data["High"]
        low = data["Low"]
        close = data["Close"]

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        # ATR = EMA des TR
        data["ATR"] = tr.ewm(span=period, adjust=False).mean()
        return data

    def analyse(self, current_price: float, atr: float, ma50: float, ma10: float) -> dict:
        """
        :param current_price: Aktueller Kurs
        :param atr: Aktueller ATR-Wert
        :param ma50: MA50 für Trendbezug
        :param ma10: MA10 für Trendbezug
        :return: Dict mit Score, Qualität und Interpretation
        """
        score = 0.0
        interpretation_list = []

        # -----------------------------
        # Bewertung basierend auf ATR
        # -----------------------------
        # Abstand ATR zum aktuellen Kurs (je näher am unteren Bereich, desto besser)
        atr_level = ma50 - current_price
        if atr_level > atr * self.atr_multiplier:
            score += 0.7
            interpretation_list.append("Preis am ATR-niedrigen Bereich – guter Einstiegszeitpunkt")
        elif atr_level < -atr * self.atr_multiplier:
            score -= 0.5
            interpretation_list.append("Preis oberhalb ATR – Risiko höher")
        else:
            score += 0.0
            interpretation_list.append("Preis innerhalb normaler Volatilität")

        # -----------------------------
        # Trendcheck über MA
        # -----------------------------
        if ma10 > ma50:
            interpretation_list.append("Kurzfristtrend bullish (MA10 > MA50)")
            score += 0.2
        elif ma10 < ma50:
            interpretation_list.append("Kurzfristtrend bearish (MA10 < MA50)")
            score -= 0.2

        # -----------------------------
        # Qualitätsstufe
        # -----------------------------
        if score >= 1.0:
            quality = "excellent"
            summary = "Exzellenter Einstieg basierend auf ATR"
            interpretation_short = "Preis und Trend günstig"
            interpretation_long = "Aktueller Kurs liegt günstig innerhalb der typischen Volatilität, Trend unterstützt Einstieg."
        elif score >= 0.5:
            quality = "good"
            summary = "Guter Einstieg basierend auf ATR"
            interpretation_short = "Preis attraktiv"
            interpretation_long = "Einstieg ist akzeptabel; Trend und Volatilität unterstützen die Entscheidung."
        elif score >= 0.0:
            quality = "neutral"
            summary = "Neutraler Einstieg"
            interpretation_short = "Preis normal"
            interpretation_long = "Keine besondere Chance oder Risiko erkannt, Einstieg vorsichtig."
        else:
            quality = "poor"
            summary = "Schlechter Einstieg"
            interpretation_short = "Preis ungünstig"
            interpretation_long = "Preis oberhalb typischer Volatilität – Risiko erhöht."

        return {
            "score": round(score, 2),
            "quality": quality,
            "summary": summary,
            "interpretation_short": interpretation_short,
            "interpretation_long": interpretation_long,
            "interpretation": " | ".join(interpretation_list)
        }

class MarketRegimeAnalysis:
    """
    Kombiniert RSI, MACD, ADX und MA zu einem übergeordneten Market-Regime
    """

    def analyse(
        self,
        rsi: dict,
        macd: dict,
        adx: dict,
        ma: dict,
        strategy_rules=None
    ) -> dict:

        # Default-Werte
        if strategy_rules is None:
            strategy_rules = {"allow_emerging_trend": False}

        market_regime = "unknown"
        trade_bias = "none"
        confidence = 0.0
        summary = "Unbekanntes Regime"
        interpretation_short = "Keine klare Marktlage erkennbar"
        interpretation_long = (
            "Die Kombination der Indikatoren liefert kein eindeutiges Bild des Marktregimes."
        )
        action_hint = "Abwarten und weitere Signale beobachten"

        # -----------------------------
        # RANGE / MEAN REVERSION
        # -----------------------------
        if adx["regime"] == "range":
            market_regime = "range_market"
            trade_bias = "mean_reversion"
            confidence = 0.4

            summary = "Seitwärtsmarkt"
            if rsi["state"] == "oversold":
                interpretation_short = "RSI überverkauft im Seitwärtsmarkt"
                interpretation_long = (
                    "Der Markt befindet sich in einer Seitwärtsphase mit "
                    "überverkauftem RSI. Dies kann eine Chance für technische "
                    "Gegenbewegungen (Long-Reversal) bieten."
                )
                action_hint = "Long-Reversal möglich, aber vorsichtig agieren"
            elif rsi["state"] == "overbought":
                interpretation_short = "RSI überkauft im Seitwärtsmarkt"
                interpretation_long = (
                    "Der Markt ist seitwärts mit überkaufter RSI-Situation, "
                    "was auf Short-Reversal Chancen hinweist."
                )
                action_hint = "Short-Reversal möglich, Risiko beachten"

        # -----------------------------
        # EMERGING TREND
        # -----------------------------
        elif adx["regime"] == "emerging_trend":
            market_regime = "transition_phase"
            trade_bias = "wait_for_confirmation"
            confidence = 0.5

            summary = "Trend im Aufbau"
            interpretation_short = "Trend entsteht, noch unsicher"
            interpretation_long = (
                "Der ADX signalisiert den Beginn eines neuen Trends. "
                "Eine Bestätigung ist jedoch noch ausstehend, daher sollten "
                "Positionen vorsichtig aufgebaut oder zunächst abgewartet werden."
            )
            action_hint = "Kleine Positionen oder abwarten"

        # -----------------------------
        # STRONG TREND
        # -----------------------------
        
        elif adx["regime"] == "strong_trend":
            market_regime = "trend_market"
            trade_bias = macd["bias"]
            confidence = 0.75

            summary = "Starker Trend"
            interpretation_short = "Trend stark und bestätigt"
            interpretation_long = "MACD + RSI + MA bestätigen den Trend."
            action_hint = "Trend folgen"

            # ⚡ MA-Check: Falls Crossover gegen Trend -> Warnung
            if ma["ma_cross"] == "bearish_cross" and macd["bias"] == "bullish":
                confidence *= 0.8
                interpretation_short += " | MA-Crossover gegen Trend!"
                interpretation_long += " MA10 hat MA50 nach unten gekreuzt – vorsichtig bei Neueinstiegen."
            elif ma["ma_cross"] == "bullish_cross" and macd["bias"] == "bearish":
                confidence *= 0.8
                interpretation_short += " | MA-Crossover gegen Trend!"
                interpretation_long += " MA10 hat MA50 nach oben gekreuzt – Vorsicht bei Short-Einstiegen."
                
        # -----------------------------
        # EXTREMER TREND / ERSCHÖPFUNG
        # -----------------------------
        elif adx["regime"] == "extreme_trend":
            market_regime = "late_trend"
            trade_bias = "risk_management"
            confidence = 0.6

            summary = "Extremer Trend"
            interpretation_short = "Sehr starker Trend mit Erschöpfungsrisiko"
            interpretation_long = (
                "Der Markt befindet sich in einem extrem starken Trend, der "
                "weiterlaufen kann, aber das Risiko einer Trendwende oder "
                "starker Rücksetzer stark gestiegen ist."
            )
            action_hint = "Gewinne sichern, Stop-Loss anpassen, vorsichtig handeln"

        else:
            summary = "Unbekanntes Regime"
            interpretation_short = "Keine klare Marktlage erkennbar"
            interpretation_long = (
                "Die Kombination der Indikatoren liefert kein eindeutiges Bild des Marktregimes."
            )
            action_hint = "Abwarten und weitere Signale beobachten"

        return {
            "market_regime": market_regime,
            "trade_bias": trade_bias,
            "confidence": round(confidence, 2),
            "summary": summary,
            "interpretation_short": interpretation_short,
            "interpretation_long": interpretation_long,
            "action_hint": action_hint
        }

    
class EntryQualityAnalysis:
    """
    Bewertet die Qualität des Einstiegs (Timing & Preis)
    unabhängig von der Trade-Entscheidung, inkl. MA & ATR
    """

    def analyse(
        self,
        bollinger: dict,
        stochastic: dict,
        market: dict,
        ma: dict,
        atr: dict  # Neu: ATR-basierte Bewertung
    ) -> dict:

        score = 0.0
        quality = "poor"
        interpretation_list = []

        # -----------------------------
        # Bollinger Bewertung
        # -----------------------------
        score += bollinger.get("score", 0)
        if bollinger["state"] in ["Below_Lower", "Lower_Half"]:
            interpretation_list.append("Preis attraktiv (Bollinger)")
        elif bollinger["state"] == "Above_Upper":
            interpretation_list.append("Preis überdehnt (Bollinger)")

        # -----------------------------
        # Stochastic Bewertung
        # -----------------------------
        score += stochastic.get("score", 0)
        if stochastic["regime"] == "Oversold_Reversal":
            interpretation_list.append("Gutes Reversal-Timing")
        elif stochastic["regime"] == "Overbought_Reversal":
            interpretation_list.append("Ungünstiges Timing")

        # -----------------------------
        # Markt-Kontext-Gewichtung
        # -----------------------------
        if market["market_regime"] == "trend_market":
            score *= 1.1
        elif market["market_regime"] == "late_trend":
            score *= 0.8

        # -----------------------------
        # MA-Check: Unterstützt oder schwächt Score
        # -----------------------------
        if ma["ma_trend"] == "bullish" and market["trade_bias"] == "trend_follow_long":
            score += 0.5
            interpretation_list.append("MA bestätigt Aufwärtstrend")
        elif ma["ma_trend"] == "bearish" and market["trade_bias"] == "trend_follow_short":
            score += 0.5
            interpretation_list.append("MA bestätigt Abwärtstrend")
        elif ma["ma_cross"] in ["bullish_cross", "bearish_cross"]:
            score -= 0.3
            interpretation_list.append("MA-Crossover gegen Trend")

        # -----------------------------
        # ATR-Check: Berücksichtigung der Volatilität
        # -----------------------------
        if atr:
            score += atr.get("score", 0)
            if "interpretation" in atr:
                interpretation_list.append(f"ATR: {atr['interpretation_short'] if 'interpretation_short' in atr else atr['interpretation']}")

        # -----------------------------
        # Qualitätsstufe
        # -----------------------------
        if score >= 1.5:
            quality = "excellent"
            summary = "Exzellenter Einstiegszeitpunkt"
            interpretation_short = "Sehr gute Kombination aus Preis, Timing und ATR"
            interpretation_long = (
                "Die Bewertung zeigt eine ausgezeichnete Einstiegsqualität mit "
                "attraktivem Preisniveau, gutem Timing und niedriger relativer Volatilität. "
                "Die Marktbedingungen unterstützen diesen Einstieg, wodurch eine hohe Wahrscheinlichkeit für einen erfolgreichen Trade besteht."
            )
            action_hint = "Einstieg klar empfohlen"
        elif score >= 0.5:
            quality = "good"
            summary = "Guter Einstiegszeitpunkt"
            interpretation_short = "Attraktives Setup mit geringem Risiko"
            interpretation_long = (
                "Die Einstiegsqualität ist gut mit positiven Signalen bei Preis, Timing und ATR. "
                "Der Markt zeigt unterstützende Tendenzen, dennoch sollten mögliche Risiken berücksichtigt werden."
            )
            action_hint = "Einstieg erwägen"
        elif score >= 0:
            quality = "neutral"
            summary = "Neutrales Einstiegs-Setup"
            interpretation_short = "Weder besonders gut noch schlecht"
            interpretation_long = (
                "Die Analyse ergibt weder eindeutige Kauf- noch Verkaufssignale. "
                "Unsicherheit besteht bezüglich des Einstiegszeitpunkts, daher ist Vorsicht geboten."
            )
            action_hint = "Abwarten oder kleine Positionen"
        else:
            quality = "poor"
            summary = "Schlechter Einstiegszeitpunkt"
            interpretation_short = "Ungünstiges Setup"
            interpretation_long = (
                "Die Bewertung deutet auf ungünstige Bedingungen für einen Einstieg hin. "
                "Preis, Timing oder ATR sprechen gegen einen Trade, daher sollte auf bessere Chancen gewartet werden."
            )
            action_hint = "Einstieg vermeiden"

        return {
            "score": round(score, 2),
            "quality": quality,
            "summary": summary,
            "interpretation_short": interpretation_short,
            "interpretation_long": interpretation_long,
            "action_hint": action_hint,
            "interpretation": " | ".join(interpretation_list)
        }


    
class TradeDecisionEngine:
    """
    Trifft eine konkrete Kauf-/Nicht-Kauf-Entscheidung
    basierend auf Market-Regime, RSI, MACD und ADX
    """
    
    def decide(
        self,
        market: dict,
        rsi: dict,
        macd: dict,
        adx: dict
    ) -> dict:
    
        # -----------------------------
        # Initialisieren (immer!)
        # -----------------------------
        strategy = market.get("strategy", "Conservative")
    
        TRADER_MATRIX_LOCAL = {
            "Conservative": ["confirmed_trend"],
            "Balanced": ["confirmed_trend", "trend_pullback"],
            "Aggressive": ["confirmed_trend", "trend_pullback", "early_momentum"],
        }
        allowed_situations = TRADER_MATRIX_LOCAL.get(strategy, ["confirmed_trend"])
    
        situation = "none"
    
        # Defaults -> garantiert stabilen Rückgabewert
        action = "HOLD"
        position_type = "none"
        confidence = 0.0
        risk_level = "low"
        reason = "Kein gültiges Setup"
        summary = "Kein Handel"
        interpretation_short = ""
        interpretation_long = ""
        action_hint = "Abwarten"
    
        bias_level = rsi.get("trend_bias", 50)
    
        # -----------------------------
        # Situation Classification (neutral)
        # -----------------------------
        if market.get("market_regime") == "trend_market":
    
            if macd.get("bias") == "bullish" and (rsi.get("value") is not None) and rsi["value"] > bias_level:
                situation = "confirmed_trend"
                confidence = market.get("confidence", 0.6)
                risk_level = "low"
                summary = "Bestätigter Trend"
                reason = "Trend + Momentum bestätigt"
    
            elif macd.get("bias") == "bullish" and (rsi.get("value") is not None) and rsi["value"] > bias_level - 8:
                situation = "trend_pullback"
                confidence = market.get("confidence", 0.6) * 0.8
                risk_level = "moderate"
                summary = "Trend-Pullback"
                reason = "Pullback im intakten Trend"
    
        elif market.get("market_regime") == "transition_phase":
    
            # frühes Momentum nur für Aggressive
            if macd.get("histogram_trend", 0) > 0:
                situation = "early_momentum"
                confidence = 0.4
                risk_level = "high"
                summary = "Frühes Momentum"
                reason = "Momentum beginnt zu drehen"
    
        # -----------------------------
        # Decision Policy (einziger Entscheidungsort)
        # -----------------------------
        if situation in allowed_situations:
            action = "BUY"
            position_type = situation
            action_hint = f"Long-Position gemäß Strategie '{strategy}' eröffnen"
        else:
            action = "HOLD"
            position_type = "none"
    
        # -----------------------------
        # EIN finaler, garantierter Return
        # -----------------------------
        return {
            "action": action,
            "position_type": position_type,
            "confidence": round(float(confidence), 2),
            "risk_level": risk_level,
            "reason": reason,
            "summary": summary,
            "interpretation_short": interpretation_short,
            "interpretation_long": interpretation_long,
            "action_hint": action_hint,
        }


class TradePlanBuilder:

    def build(self, decision: dict, entry: dict) -> dict:

        if decision["action"] not in ["BUY", "SELL"]:
            return {"execute": False, "reason": "Kein Handelssignal"}

        if entry["quality"] == "poor":
            return {
                "execute": False,
                "reason": "Entry-Qualität zu schlecht"
            }

        size_factor = {
            "excellent": 1.0,
            "good": 0.7,
            "neutral": 0.4
        }.get(entry["quality"], 0)

        return {
            "execute": True,
            "direction": decision["action"],
            "size_factor": size_factor,
            "risk_level": decision["risk_level"],
            "confidence": decision["confidence"]
        }


class PositionSizer:
    def __init__(self, konto_groesse: float):
        """
        Initialisiert den Positionsgrößen-Rechner.

        Args:
            konto_groesse (float): Gesamtes Kapital (z.B. 10.000 €)
        """
        self.konto_groesse = konto_groesse  # z.B. 10000 €

    def berechne_positionsgroesse(
        self,
        einstiegskurs: float,
        stop_loss_kurs: float,
        risiko_prozent: float = 1.0,       # Prozentualer Risikoanteil am Konto, z.B. 1%
        confidence: float = 1.0,           # Vertrauen in die Trade-Entscheidung (0 bis 1)
        risiko_level: str = "moderate"     # Risikokategorie: low, moderate, high
    ) -> dict:

        # Berechnung des absoluten Risikobetrags in Euro
        risk_amount = self.konto_groesse * (risiko_prozent / 100)

        # Abstand zwischen Einstiegs- und Stop-Loss-Kurs
        stop_loss_abstand = abs(einstiegskurs - stop_loss_kurs)

        if stop_loss_abstand == 0:
            return {
                "error": "Stop-Loss Abstand darf nicht 0 sein",
                "message": "Der Abstand zwischen Einstiegs- und Stop-Loss-Kurs darf nicht null sein, "
                           "da sonst keine Positionsgröße berechnet werden kann."
            }

        # Berechnung der Basis-Positionsgröße (Anzahl Aktien, Kontrakte etc.)
        base_position_size = risk_amount / stop_loss_abstand

        # Multiplikator für Risiko-Level (z.B. konservativer bei hohem Risiko)
        risiko_faktoren = {
            "low": 1.2,       # Leicht größere Position bei geringem Risiko möglich
            "moderate": 1.0,  # Standard
            "high": 0.8       # Position wird verkleinert bei hohem Risiko
        }
        risiko_faktor = risiko_faktoren.get(risiko_level, 1.0)

        # Adjustierte Positionsgröße unter Berücksichtigung des Konfidenzwerts
        position_size = base_position_size * risiko_faktor * confidence

        # Interpretationstexte für UI und Nutzerfreundlichkeit
        summary = f"Empfohlene Positionsgröße basiert auf einem Risiko von {risiko_prozent}% " \
                  f"des Kontos ({risk_amount} €) und einem Stop-Loss-Abstand von {round(stop_loss_abstand, 4)}."

        interpretation_short = f"Positionsgröße: {round(position_size, 2)} Einheiten"

        interpretation_long = (
            f"Das Risiko pro Trade wird auf {round(risiko_prozent, 2)}% des Kontos begrenzt, "
            f"was {round(risk_amount, 2)} € entspricht. Die Positionsgröße wird anhand des Abstandes "
            f"zwischen Einstieg ({einstiegskurs}) und Stop-Loss ({stop_loss_kurs}) berechnet, "
            f"um das Risiko zu steuern. Ein Risiko-Level '{risiko_level}' "
            f"passt die Positionsgröße entsprechend an, ebenso wie das Vertrauen in den Trade "
            f"mit einem Faktor von {round(confidence, 2)} berücksichtigt wird."
        )

        action_hint = (
            "Stelle sicher, dass Stop-Loss und Einstiegsniveau sinnvoll gesetzt sind, "
            "um unerwartete Verluste zu vermeiden. Diese Positionsgröße soll das Risiko "
            "kontrollieren und ist kein Garant für Gewinn."
        )

        return {
            "position_size": round(position_size, 2),
            "risk_amount": round(risk_amount, 2),
            "stop_loss_abstand": round(stop_loss_abstand, 4),
            "confidence": round(confidence, 2),
            "risiko_level": risiko_level,
            "summary": summary,
            "interpretation_short": interpretation_short,
            "interpretation_long": interpretation_long,
            "action_hint": action_hint
        }


"""
🛑 Stop-Loss & 🎯 Take-Profit je Market-Regime
Regime	Stop-Loss Abstand (in %)	Take-Profit Abstand (in %)	Erklärung
Bullish	3 % unter Einstieg	6 % über Einstieg	Etwas enger Stop-Loss, da Markt klar im Aufwärtstrend
Bearish	2 % über Einstieg (für Short)	4 % unter Einstieg (für Short)	Strenger Stop-Loss, um Risiko zu begrenzen
Sideways	1.5 % unter/über Einstieg	3 % über/unter Einstieg	Engere Stops wegen Seitwärtsbewegung, Take-Profit kleiner
"""


class TradeRiskManager:
    def __init__(self, einstiegskurs: float, regime: str):
        self.einstiegskurs = float(einstiegskurs)
        self.regime = (regime or "").lower()

    
    def sl_tp_by_atr(self, atr: float, position_typ: str = "long", mults: dict | None = None) -> dict:
        # Default (falls keine Mults übergeben)
        sl_mult = 1.2
        tp_mult = 1.8
    
        # 1) bevorzugt: extern übergebene Multiplikatoren nutzen
        if mults and "sl" in mults and "tp" in mults:
            sl_mult, tp_mult = float(mults["sl"]), float(mults["tp"])
        else:
            # 2) fallback: interne Regime-Defaults
            if self.regime == "trend_market":
                sl_mult, tp_mult = 1.5, 3.0
            elif self.regime == "range_market":
                sl_mult, tp_mult = 1.0, 1.5
            elif self.regime in ("late_trend", "transition_phase"):
                sl_mult, tp_mult = 1.2, 1.8
        
        atr = float(atr or 0.0)
        if atr <= 0:
            # Fallback: 2%/4% in absoluten Notfällen
            atr = self.einstiegskurs * 0.02
            sl_mult, tp_mult = 1.0, 2.0

        if position_typ == "long":
            stop_loss  = self.einstiegskurs - sl_mult * atr
            take_profit = self.einstiegskurs + tp_mult * atr
        elif position_typ == "short":
            stop_loss  = self.einstiegskurs + sl_mult * atr
            take_profit = self.einstiegskurs - tp_mult * atr
        else:
            raise ValueError("position_typ muss 'long' oder 'short' sein")

        return {
            "stop_loss": round(stop_loss, 4),
            "take_profit": round(take_profit, 4),
            "sl_mult_atr": sl_mult,
            "tp_mult_atr": tp_mult,
            "regime": self.regime,
            "position_typ": position_typ
        }

    def stop_loss_take_profit(self, position_typ="long", use_atr=False, atr: float = None) -> dict:
        """
        Kompatibel zur bisherigen API:
        - use_atr=True: ATR-basierte SL/TP via sl_tp_by_atr(...)
        - use_atr=False: prozent-basierte SL/TP wie bisher
        """
        if use_atr:
            return self.sl_tp_by_atr(atr=atr, position_typ=position_typ)

        # ---- bestehende Prozent-Logik (unverändert) ----
        stop_loss_pct = 0.03
        take_profit_pct = 0.06
        if self.regime == "bullish":
            stop_loss_pct, take_profit_pct = 0.03, 0.06
        elif self.regime == "bearish":
            stop_loss_pct, take_profit_pct = 0.02, 0.04
        elif self.regime == "sideways":
            stop_loss_pct, take_profit_pct = 0.015, 0.03
        else:
            stop_loss_pct, take_profit_pct = 0.03, 0.05

        if position_typ == "long":
            stop_loss  = self.einstiegskurs * (1 - stop_loss_pct)
            take_profit = self.einstiegskurs * (1 + take_profit_pct)
        elif position_typ == "short":
            stop_loss  = self.einstiegskurs * (1 + stop_loss_pct)
            take_profit = self.einstiegskurs * (1 - take_profit_pct)
        else:
            raise ValueError("position_typ muss 'long' oder 'short' sein")

        return {
            "stop_loss": round(stop_loss, 4),
            "take_profit": round(take_profit, 4),
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "regime": self.regime,
            "position_typ": position_typ
        }
    
class SignalGenerator:

    def __init__(self, thresholds):
        self.thresholds = thresholds
        self.engine = TradeDecisionEngine()

    def generate_signals(
        self,
        full_data: pd.DataFrame,
        min_len_window: int = 20
    ) -> pd.DataFrame:
    
        signale = []
        thr = self.thresholds
    
        rsi_analysis = RSIAnalysis(
            oversold=thr["RSI"]["oversold"],
            overbought=thr["RSI"]["overbought"],
            bullish_floor=thr["RSI"]["bullish_floor"],
            bearish_ceiling=thr["RSI"]["bearish_ceiling"],
        )
    
        macd_analysis = MACDAnalysis()
        adx_analysis = ADXAnalysis(
            weak_trend=thr["ADX"]["weak_trend"],
            strong_trend=thr["ADX"]["strong_trend"],
            extreme_trend=thr["ADX"]["extreme_trend"],
        )
        ma_analysis = MAAnalysis()
        market_analysis = MarketRegimeAnalysis()
    
        action_map = {
            "BUY": "🟢 Kaufen",
            "SELL": "🔴 Verkaufen",
            "HOLD": "🟡 Halten",
            "WAIT": "🟡 Halten",
            "NO_TRADE": "🟡 Halten",
            "REDUCE": "🟡 Halten",
        }
    
        for i in range(min_len_window, len(full_data)):
            fenster = full_data.iloc[: i + 1]
    
            rsi_result = rsi_analysis.analyse(fenster)
            rsi_result["trend_bias"] = thr["RSI"]["trend_bias"]
    
            macd_result = macd_analysis.analyse(fenster)
            adx_result = adx_analysis.analyse(fenster)
            ma_result = ma_analysis.analyse(fenster)
            strategy_rules = STRATEGY_RULES.get(self.strategy, STRATEGY_RULES["Conservative"])
            market_result = market_analysis.analyse(
                rsi_result, macd_result, adx_result, ma_result, strategy_rules
            )
            market_result["strategy"] = self.strategy
    
            decision = self.engine.decide(
                market_result, rsi_result, macd_result, adx_result
            )
    
            action = decision.get("action", "HOLD")
            
            signale.append({
                "Datum": full_data.index[i],
                "Entscheidung": action_map.get(action, "🟡 Halten"),
                "Positionstyp": decision.get("position_type", "none"),
                "Confidence": decision.get("confidence", 0.0),
                "RiskLevel": decision.get("risk_level", "unknown"),
            })

        return pd.DataFrame(signale)


class BuySignalEvaluator:

    @staticmethod
    def filter_buy_signals(signals_df: pd.DataFrame) -> pd.DataFrame:
        return signals_df[
            signals_df["Entscheidung"].str.contains("Kaufen")
        ].copy()

    @staticmethod
    def cluster_periods(kaufsignale_df, max_gap_days=5):
        # ⛔ Edge Case: keine Kaufsignale
        if kaufsignale_df is None or kaufsignale_df.empty:
            return []
        daten = kaufsignale_df.sort_values("Datum")["Datum"].tolist()
        # ⛔ zusätzliche Sicherheit (z.B. falls Datum-Spalte leer ist)
        if not daten:
            return []
        perioden = []

        start = prev = daten[0]
        for d in daten[1:]:
            if (d - prev).days <= max_gap_days:
                prev = d
            else:
                perioden.append((start, prev))
                start = prev = d

        perioden.append((start, prev))
        return perioden

    @staticmethod
    def evaluate_periods(perioden, full_data, Auswertung_tage, min_veraenderung):
        bewertungen = []

        for start, end in perioden:
            start_kurs = full_data.loc[end, "Close"]
            idx = full_data.index.get_loc(end)
            max_kurs = full_data.iloc[idx:idx+Auswertung_tage+1]["Close"].max()

            diff = (max_kurs - start_kurs) / start_kurs

            bewertungen.append({
                "Start": start,
                "Ende": end,
                "Signal": diff >= min_veraenderung,
                "Kurs_Diff": diff,
            })

        return pd.DataFrame(bewertungen)

class SwingSignalService:

    
    def __init__(elf, thresholds, strategy: str):
        self.strategy = strategy
        self.generator = SignalGenerator(thresholds, strategy)
        self.evaluator = BuySignalEvaluator()

    def run_analysis(
        self,
        full_data,
        Auswertung_tage,
        min_veraenderung,
        market,
        rsi,
        macd,
        adx
    ):
        signals = self.generator.generate_signals(
            full_data
        )

        buys = self.evaluator.filter_buy_signals(signals)

        if buys.empty:
            return {"signals": signals}

        perioden = self.evaluator.cluster_periods(buys)
        bewertung = self.evaluator.evaluate_periods(
            perioden, full_data, Auswertung_tage, min_veraenderung
        )

        return {
            "signals": signals,
            "buy_signals": buys,
            "perioden_bewertung": bewertung,
            "trefferquote": bewertung["Signal"].mean() * 100
        }
