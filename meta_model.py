# Training Pipeline (V2)

## Walk-Forward Optimizer (WFO)
Rolling train/test optimization to reduce overfitting:
1) Split history into sequential rolls.
2) For each roll, grid-search parameters on TRAIN.
3) Generate entry events via RuleEngine.
4) Label entry events on TRAIN and TEST using Triple-Barrier.
5) Select params by best out-of-sample hit rate (optionally ignore neutral labels).
6) Apply stability rules (update only on meaningful improvement; clamp RSI changes).

Outputs:
- config/learned_params.json per ticker
- reports/wfo_<date>.json summary

## Meta-Label Model (optional)
Train a classifier on entry events:
- y=1 if triple-barrier label==+1 else 0
- features at entry day (and lags)
- save model and use p_success to suppress weak buys
