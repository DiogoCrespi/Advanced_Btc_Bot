---
name: execution
description: "Skill for the Execution area of Advanced_Btc_Bot. 18 symbols across 6 files."
---

# Execution

18 symbols | 6 files | Cohesion: 69%

## When to Use

- Working with code in `logic/`
- Understanding how generate_mock_data, run_backtest_example, load_data work
- Modifying execution-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `logic/execution/backtest_engine.py` | load_data, get_balance, _update_order_price_bounds, step, _execute_order (+3) |
| `logic/execution/performance.py` | PerformanceAnalyzer, _pair_trades, calculate_metrics, generate_equity_curve, print_summary |
| `tools/run_backtest.py` | generate_mock_data, run_backtest_example |
| `logic/execution/binance_testnet.py` | BinanceTestnet |
| `logic/execution/binance_live.py` | BinanceLive |
| `logic/execution/base.py` | BaseExchange |

## Entry Points

Start here when exploring this area:

- **`generate_mock_data`** (Function) — `tools/run_backtest.py:6`
- **`run_backtest_example`** (Function) — `tools/run_backtest.py:26`
- **`load_data`** (Function) — `logic/execution/backtest_engine.py:47`
- **`get_balance`** (Function) — `logic/execution/backtest_engine.py:166`
- **`step`** (Function) — `logic/execution/backtest_engine.py:69`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `PerformanceAnalyzer` | Class | `logic/execution/performance.py` | 5 |
| `BinanceTestnet` | Class | `logic/execution/binance_testnet.py` | 7 |
| `BinanceLive` | Class | `logic/execution/binance_live.py` | 7 |
| `BaseExchange` | Class | `logic/execution/base.py` | 3 |
| `BacktestEngine` | Class | `logic/execution/backtest_engine.py` | 7 |
| `generate_mock_data` | Function | `tools/run_backtest.py` | 6 |
| `run_backtest_example` | Function | `tools/run_backtest.py` | 26 |
| `load_data` | Function | `logic/execution/backtest_engine.py` | 47 |
| `get_balance` | Function | `logic/execution/backtest_engine.py` | 166 |
| `step` | Function | `logic/execution/backtest_engine.py` | 69 |
| `create_order` | Function | `logic/execution/backtest_engine.py` | 170 |
| `cancel_order` | Function | `logic/execution/backtest_engine.py` | 202 |
| `calculate_metrics` | Function | `logic/execution/performance.py` | 67 |
| `generate_equity_curve` | Function | `logic/execution/performance.py` | 139 |
| `print_summary` | Function | `logic/execution/performance.py` | 159 |
| `_update_order_price_bounds` | Function | `logic/execution/backtest_engine.py` | 32 |
| `_execute_order` | Function | `logic/execution/backtest_engine.py` | 103 |
| `_pair_trades` | Function | `logic/execution/performance.py` | 14 |

## How to Explore

1. `gitnexus_context({name: "generate_mock_data"})` — see callers and callees
2. `gitnexus_query({query: "execution"})` — find related execution flows
3. Read key files listed above for implementation details
