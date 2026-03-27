# Trading Signal Spec (V2) – Rule Engine + Triple-Barrier

This document captures the agreed system behavior:

## Inputs (Data Contract)
The engine consumes a DataFrame containing at least these columns:
- Close
- BB_Upper, BB_Lower, BB_Middle
- RSI
- MACD, MACD_Signal, MACD_Hist
- MA10, MA50
- ADX, +DI, -DI

## Derived Features
- bb_pos = (Close - BB_Lower) / (BB_Upper - BB_Lower)
- hist_rising = MACD_Hist(t) > MACD_Hist(t-1)
- macd_cross_up = (MACD(t) > MACD_Signal(t)) and (MACD(t-1) <= MACD_Signal(t-1))
- downtrend_strength = (ADX > adx_thr) and (-DI > +DI)

## Triple-Barrier Labels
For each entry event at t_entry:
- PT = entry_price*(1+pt_pct)
- SL = entry_price*(1-sl_pct)
- Vertical barrier = t_entry + max_hold_days
Label is the first barrier touched:
+1: PT first
-1: SL first
0: time first

Defaults: pt_pct=0.08, sl_pct=0.04, max_hold_days=60.

## State Machine
States: FLAT, ENTRY_ACTIVE, VALIDATED, HOLDING, EXITED

Transitions:
- FLAT -> ENTRY_ACTIVE (BUY emitted only on this day) when entry conditions hold.
- ENTRY_ACTIVE -> VALIDATED when any validation condition holds.
- ENTRY_ACTIVE -> HOLDING when entry window expires without validation OR setup erodes.
- VALIDATED/HOLDING -> EXITED (SELL emitted only on this day) when TP hit OR invalidation triggers.
- EXITED -> FLAT on next evaluation.

Outputs:
- BUY only on FLAT->ENTRY_ACTIVE
- SELL only on *->EXITED
- otherwise HOLD

## Runtime Policy Modes
- rules_only: use global defaults
- rules_wfo: merge in per-ticker learned params
- rules_wfo_meta: apply meta filter; if p_success < threshold suppress BUY (emit HOLD + reason)
