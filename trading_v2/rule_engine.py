from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import pandas as pd

from .features import build_features
from .state_store import TradeState, load_state, save_state
from .config_loader import load_global, load_learned, load_ui_policy, resolve_params
from .meta_model import MetaModel

@dataclass
class Decision:
    signal: str  # BUY/SELL/HOLD
    state: str
    confidence: float
    reasons: List[str]
    meta: Dict[str, Any]


class RuleEngineV2:
    def __init__(self, meta_model: Optional[MetaModel] = None):
        self.global_cfg = load_global()
        self.learned = load_learned()
        self.policy = load_ui_policy()
        self.meta_model = meta_model or MetaModel(None)

    def evaluate(self, symbol: str, df: pd.DataFrame) -> Decision:
        # ✅ IMMER definieren – Baseline (Conservative)
        params = {
            "rsi_thr": 35,
            "bb_pos_thr": 0.20,
            "require_hist_rising": False,
            "entry_window_days": 4,
            "validation_bonus": 15,
            "erosion_penalty": 8,
            "erosion_margin": 5,
        }
        
        # --- config ---
        lifecycle = self.global_cfg.get('lifecycle', {})
        labeling = self.global_cfg.get('labeling', {})
        risk = self.global_cfg.get('risk', {})
        entry_window_days = int(params.get('entry_window_days', 4))
        validation_bonus = float(params.get('validation_bonus', 15))
        erosion_penalty = float(params.get('erosion_penalty', 8))
        erosion_margin = float(params.get('erosion_margin', 5))
        adx_thr = float(risk.get('adx_thr', 30))

        mode = self.policy.mode
        params = resolve_params(
            symbol,
            mode=self.policy.mode,
            global_cfg=self.global_cfg,
            learned=self.learned,
            active_profile=getattr(self.policy, "active_profile", "Conservative"),
        )
        if resolved:
                params.update(resolved)
        rsi_thr = float(params.get('rsi_thr', 35))
        bb_pos_thr = float(params.get('bb_pos_thr', 0.20))
        require_hist_rising = bool(params.get('require_hist_rising', False))

        # --- features ---
        feat = build_features(df, adx_thr=adx_thr)
        today = str(df.index[-1].date()) if hasattr(df.index[-1], 'date') else str(df.index[-1])

        # --- load state ---
        st = load_state(symbol)
        reasons: List[str] = []
        meta_info: Dict[str, Any] = {}

        # helper: avoid duplicate BUY/SELL same day
        def already_emitted(sig: str) -> bool:
            return st.last_signal_day == f"{today}:{sig}"
        def mark_emitted(sig: str) -> None:
            st.last_signal_day = f"{today}:{sig}"

        # --- compute entry conditions ---
        entry_ok = True
        if feat['rsi'] <= rsi_thr:
            reasons.append('rsi_low')
        else:
            entry_ok = False

        if (feat['bb_pos'] <= bb_pos_thr) or (feat['close'] <= feat['bb_lower']):
            reasons.append('bb_lower_touch')
        else:
            entry_ok = False

        if feat['macd_hist'] < 0:
            reasons.append('macd_hist_neg')
        else:
            entry_ok = False

        if require_hist_rising:
            if feat['hist_rising']:
                reasons.append('hist_rising')
            else:
                entry_ok = False

        # --- validation conditions (any) ---
        validated_now = False
        if feat['macd_cross_up']:
            validated_now = True
            reasons.append('macd_cross_up')
        if feat['macd_hist'] >= 0:
            validated_now = True
            reasons.append('hist_nonneg')
        if feat['close'] >= feat['bb_middle']:
            validated_now = True
            reasons.append('close_above_bb_mid')

        # --- exit conditions ---
        tp_hit = False
        if st.entry_price is not None:
            pt = float(st.entry_price) * (1.0 + float(labeling.get('pt_pct', 0.08)))
            if feat['close'] >= pt:
                tp_hit = True
                reasons.append('tp_hit')

        # operationalized invalidation (minimal, deterministic)
        invalidation = False
        if st.entry_price is not None:
            # 1) downtrend strength
            if feat['downtrend_strength']:
                reasons.append('downtrend_strength')
                # 2) new low vs last N bars (use 5 as deterministic)
                N = 5
                if len(df) > N:
                    recent = df.iloc[-N:]
                    if float(feat['close']) <= float(recent['Close'].min()):
                        reasons.append('new_low')
                        # 3) histogram falling multiple days
                        if len(df) >= 4:
                            h = df['MACD_Hist'].iloc[-4:]
                            if float(h.iloc[-1]) < float(h.iloc[-2]) < float(h.iloc[-3]):
                                reasons.append('hist_falling')
                                invalidation = True

        # --- state machine ---
        signal = 'HOLD'

        if st.state == 'EXITED':
            st = TradeState()  # reset

        if st.state == 'FLAT':
            if entry_ok:
                st.state = 'ENTRY_ACTIVE'
                st.entry_day = today
                st.entry_price = float(feat['close'])  # entry_price_source: close
                st.confidence = 0.0
                signal = 'BUY'
                reasons.append('enter')
        elif st.state == 'ENTRY_ACTIVE':
            # validate
            if validated_now:
                st.state = 'VALIDATED'
                st.confidence += validation_bonus
                reasons.append('validated')
            else:
                # check window expiry
                try:
                    d0 = pd.Timestamp(st.entry_day)
                    d1 = pd.Timestamp(today)
                    days = int((d1 - d0).days)
                except Exception:
                    days = entry_window_days
                if days > entry_window_days:
                    st.state = 'HOLDING'
                    reasons.append('entry_window_expired')
                else:
                    reasons.append('waiting_validation')
                # erosion: RSI and bb_pos well above threshold
                if feat['rsi'] > (rsi_thr + erosion_margin) and feat['bb_pos'] > (bb_pos_thr + 0.10):
                    st.state = 'HOLDING'
                    st.confidence = max(0.0, st.confidence - erosion_penalty)
                    reasons.append('setup_eroded')
        elif st.state in ('VALIDATED', 'HOLDING'):
            if tp_hit or invalidation:
                st.state = 'EXITED'
                signal = 'SELL'
                reasons.append('exit')
        else:
            # unknown -> reset
            st = TradeState()

        # --- meta policy ---
        if signal == 'BUY' and mode == 'rules_wfo_meta' and self.policy.meta_enabled:
            p = float(self.meta_model.predict_p_success(feat))
            meta_info = {'p_success': p, 'threshold': self.policy.meta_threshold, 'applied': True}
            if p < self.policy.meta_threshold:
                # suppress BUY
                signal = 'HOLD'
                reasons.append('meta_suppressed')
        else:
            if mode == 'rules_wfo_meta':
                meta_info = {'applied': False}

        # de-dup
        if signal in ('BUY','SELL') and already_emitted(signal):
            signal = 'HOLD'
            reasons.append('dedup')
        elif signal in ('BUY','SELL'):
            mark_emitted(signal)

        save_state(symbol, st)

        return Decision(signal=signal, state=st.state, confidence=float(st.confidence), reasons=sorted(set(reasons)), meta=meta_info)
