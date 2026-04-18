---
name: tools
description: "Skill for the Tools area of Advanced_Btc_Bot. 29 symbols across 13 files."
---

# Tools

29 symbols | 13 files | Cohesion: 90%

## When to Use

- Working with code in `tools/`
- Understanding how test_ml_prepare_features, order_flow_logic, verify_integration work
- Modifying tools-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tools/time_machine_simulator.py` | __init__, fetch_long_history, run_simulation, finish_report |
| `tools/optimizer.py` | __init__, StrategyOptimizer, run_backtest, run_comparative_analysis |
| `tools/backtest_stat_arb.py` | close_trade, run, execute_loop, report |
| `tools/scanner_cofre.py` | log_event, escanear_continuamente, gerar_ordem_de_servico |
| `tools/features.py` | apply_all_features, add_macd, add_bb |
| `tools/init_simulation.py` | ensure_dir, init_simulation |
| `tools/backtest_cash_carry.py` | run, report |
| `tools/backtest_basis.py` | run, report |
| `logic/order_flow_logic.py` | OrderFlowLogic |
| `logic/ml_brain.py` | MLBrain |

## Entry Points

Start here when exploring this area:

- **`test_ml_prepare_features`** (Function) — `tests/unit/test_tier2_ml.py:37`
- **`order_flow_logic`** (Function) — `tests/unit/test_order_flow_logic.py:7`
- **`verify_integration`** (Function) — `tests/integration/verify_merge.py:5`
- **`close_trade`** (Function) — `tools/backtest_stat_arb.py:15`
- **`run`** (Function) — `tools/backtest_stat_arb.py:33`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `OrderFlowLogic` | Class | `logic/order_flow_logic.py` | 4 |
| `MLBrain` | Class | `logic/ml_brain.py` | 7 |
| `StrategyOptimizer` | Class | `tools/optimizer.py` | 8 |
| `test_ml_prepare_features` | Function | `tests/unit/test_tier2_ml.py` | 37 |
| `order_flow_logic` | Function | `tests/unit/test_order_flow_logic.py` | 7 |
| `verify_integration` | Function | `tests/integration/verify_merge.py` | 5 |
| `close_trade` | Function | `tools/backtest_stat_arb.py` | 15 |
| `run` | Function | `tools/backtest_stat_arb.py` | 33 |
| `execute_loop` | Function | `tools/backtest_stat_arb.py` | 63 |
| `report` | Function | `tools/backtest_stat_arb.py` | 104 |
| `fetch_long_history` | Function | `tools/time_machine_simulator.py` | 31 |
| `run_simulation` | Function | `tools/time_machine_simulator.py` | 54 |
| `finish_report` | Function | `tools/time_machine_simulator.py` | 125 |
| `log_event` | Function | `tools/scanner_cofre.py` | 29 |
| `escanear_continuamente` | Function | `tools/scanner_cofre.py` | 37 |
| `gerar_ordem_de_servico` | Function | `tools/scanner_cofre.py` | 74 |
| `run_backtest` | Function | `tools/optimizer.py` | 17 |
| `run_comparative_analysis` | Function | `tools/optimizer.py` | 128 |
| `apply_all_features` | Function | `tools/features.py` | 3 |
| `add_macd` | Function | `tools/features.py` | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Logic | 2 calls |

## How to Explore

1. `gitnexus_context({name: "test_ml_prepare_features"})` — see callers and callees
2. `gitnexus_query({query: "tools"})` — find related execution flows
3. Read key files listed above for implementation details
