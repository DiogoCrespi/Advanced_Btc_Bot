---
name: unit
description: "Skill for the Unit area of Advanced_Btc_Bot. 102 symbols across 26 files."
---

# Unit

102 symbols | 26 files | Cohesion: 84%

## When to Use

- Working with code in `tests/`
- Understanding how compute_ratio_features, get_signal, calc_pnl_btc work
- Modifying unit-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tests/unit/test_stat_arb_logic.py` | test_get_signal_nan, test_get_signal_short, test_get_signal_long, test_get_signal_mean_reversion, test_get_signal_no_action (+9) |
| `tests/unit/test_tribunal.py` | test_macro_veto, test_macro_veto_not_applied_for_sell, test_failure_analogy_veto, test_ancestral_veto_divergence, test_ancestral_veto_caution (+7) |
| `tests/unit/test_tier3_rotation.py` | test_xaut_analyzer_features, test_compute_ratio_features_logic, test_xaut_buy_signal, test_xaut_sell_signal, test_is_dca_allowed (+3) |
| `tests/unit/test_funding_logic.py` | test_calculate_annualized_funding_positive, test_calculate_annualized_funding_zero, test_calculate_annualized_funding_negative, test_get_signal_enter_long, test_get_signal_exit (+2) |
| `logic/xaut_logic.py` | XAUTAnalyzer, compute_ratio_features, get_signal, calc_pnl_btc, calc_pnl_pct (+1) |
| `tests/unit/test_macro_radar.py` | test_get_macro_score_neutral, test_get_macro_score_extreme_positive, test_get_macro_score_extreme_negative, test_get_macro_score_clamping, test_is_risk_off_extreme (+1) |
| `logic/gap_logic.py` | GapLogic, detect_cme_gaps, detect_fvg, classify_gap, evaluate_opportunity |
| `tests/unit/test_gap_logic.py` | test_detect_fvg_bullish, test_detect_fvg_bearish, test_classify_breakaway, test_classify_exhaustion, test_gap_logic_insufficient_data |
| `logic/macro_radar.py` | MacroRadar, get_macro_score, is_risk_off_extreme, get_recommended_position_mult |
| `logic/stat_arb_logic.py` | StatArbLogic, get_signal, is_spread_profitable, calculate_zscore |

## Entry Points

Start here when exploring this area:

- **`compute_ratio_features`** (Function) — `logic/xaut_logic.py:26`
- **`get_signal`** (Function) — `logic/xaut_logic.py:63`
- **`calc_pnl_btc`** (Function) — `logic/xaut_logic.py:121`
- **`calc_pnl_pct`** (Function) — `logic/xaut_logic.py:124`
- **`is_dca_allowed`** (Function) — `logic/xaut_logic.py:129`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `XAUTAnalyzer` | Class | `logic/xaut_logic.py` | 5 |
| `MacroRadar` | Class | `logic/macro_radar.py` | 4 |
| `GapLogic` | Class | `logic/gap_logic.py` | 4 |
| `RiskManager` | Class | `logic/risk_manager.py` | 18 |
| `StatArbLogic` | Class | `logic/stat_arb_logic.py` | 4 |
| `FundingLogic` | Class | `logic/funding_logic.py` | 4 |
| `CoinGeckoClient` | Class | `logic/coingecko_client.py` | 4 |
| `compute_ratio_features` | Function | `logic/xaut_logic.py` | 26 |
| `get_signal` | Function | `logic/xaut_logic.py` | 63 |
| `calc_pnl_btc` | Function | `logic/xaut_logic.py` | 121 |
| `calc_pnl_pct` | Function | `logic/xaut_logic.py` | 124 |
| `is_dca_allowed` | Function | `logic/xaut_logic.py` | 129 |
| `test_xaut_analyzer_features` | Function | `tests/unit/test_tier3_rotation.py` | 13 |
| `test_compute_ratio_features_logic` | Function | `tests/unit/test_tier3_rotation.py` | 22 |
| `test_xaut_buy_signal` | Function | `tests/unit/test_tier3_rotation.py` | 60 |
| `test_xaut_sell_signal` | Function | `tests/unit/test_tier3_rotation.py` | 72 |
| `test_is_dca_allowed` | Function | `tests/unit/test_tier3_rotation.py` | 83 |
| `test_xaut_calc_pnl` | Function | `tests/unit/test_tier3_rotation.py` | 129 |
| `test_xaut_get_signal_branches` | Function | `tests/unit/test_tier3_rotation.py` | 175 |
| `make_df` | Function | `tests/unit/test_tier3_rotation.py` | 200 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Logic | 2 calls |
| Scripts | 1 calls |

## How to Explore

1. `gitnexus_context({name: "compute_ratio_features"})` — see callers and callees
2. `gitnexus_query({query: "unit"})` — find related execution flows
3. Read key files listed above for implementation details
