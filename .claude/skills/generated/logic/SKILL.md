---
name: logic
description: "Skill for the Logic area of Advanced_Btc_Bot. 106 symbols across 30 files."
---

# Logic

106 symbols | 30 files | Cohesion: 83%

## When to Use

- Working with code in `logic/`
- Understanding how list_all, run_comparison, parse_expiry work
- Modifying logic-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `logic/news_fetcher.py` | NewsFetcher, fetch_async, _fetch_newsapi, _fetch_tavily, _update_cache (+6) |
| `logic/risk_manager.py` | _log_audit, _trigger_cooldown, is_in_cooldown, check_max_drawdown, check_exit_conditions (+4) |
| `logic/market_memory.py` | MarketMemory, close, record_context_and_decision, get_historical_conviction, record_outcome (+3) |
| `logic/watchdog.py` | Watchdog, run, _check_ram, _check_latency, _check_neo4j (+2) |
| `logic/evolutionary_engine.py` | EvolutionaryEngine, DNA, mutate, clip, __init__ (+2) |
| `logic/intelligence_manager.py` | __init__, fetch_macro_data, fetch_news_sentiment, calculate_macro_risk, get_market_regime (+2) |
| `logic/ml_brain.py` | save_model, load_model, prepare_features, train, predict_signal |
| `logic/strategist_agent.py` | StrategistAgent, assess_trade, run, __init__, _build_workflow |
| `logic/usdt_brl_logic.py` | UsdtBrlLogic, compute_features, _evaluate_buy_signal, _evaluate_sell_signal, get_signal |
| `logic/basis_logic.py` | BasisLogic, parse_expiry, calculate_annualized_yield, get_best_contract |

## Entry Points

Start here when exploring this area:

- **`list_all`** (Function) — `tools/list_yields.py:5`
- **`run_comparison`** (Function) — `tools/compare_basis_yields.py:9`
- **`parse_expiry`** (Function) — `logic/basis_logic.py:8`
- **`calculate_annualized_yield`** (Function) — `logic/basis_logic.py:23`
- **`get_best_contract`** (Function) — `logic/basis_logic.py:38`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `BasisLogic` | Class | `logic/basis_logic.py` | 4 |
| `Watchdog` | Class | `logic/watchdog.py` | 11 |
| `ConsensusTribunal` | Class | `logic/tribunal.py` | 0 |
| `LocalOracle` | Class | `logic/local_oracle.py` | 12 |
| `EvolutionaryEngine` | Class | `logic/evolutionary_engine.py` | 57 |
| `StrategistAgent` | Class | `logic/strategist_agent.py` | 17 |
| `UsdtBrlLogic` | Class | `logic/usdt_brl_logic.py` | 4 |
| `NewsFetcher` | Class | `logic/news_fetcher.py` | 64 |
| `DNA` | Class | `logic/evolutionary_engine.py` | 6 |
| `MarketMemory` | Class | `logic/market_memory.py` | 13 |
| `MiroFishClient` | Class | `logic/mirofish_client.py` | 9 |
| `IntelligenceManager` | Class | `logic/intelligence_manager.py` | 8 |
| `list_all` | Function | `tools/list_yields.py` | 5 |
| `run_comparison` | Function | `tools/compare_basis_yields.py` | 9 |
| `parse_expiry` | Function | `logic/basis_logic.py` | 8 |
| `calculate_annualized_yield` | Function | `logic/basis_logic.py` | 23 |
| `get_best_contract` | Function | `logic/basis_logic.py` | 38 |
| `test_basis_calculation` | Function | `tests/unit/test_tier1_basis.py` | 11 |
| `test_best_contract` | Function | `tests/unit/test_tier1_basis.py` | 26 |
| `test_basis_zero_price_handling` | Function | `tests/unit/test_tier1_basis.py` | 36 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Get_sentiment_keywords → Warning` | cross_community | 5 |
| `Get_sentiment_keywords → Debug` | cross_community | 4 |
| `Get_sentiment_keywords → _maybe_reset_flags` | cross_community | 4 |
| `Get_sentiment_keywords → Info` | cross_community | 4 |
| `Analyze_frequency → Get_first_hit` | cross_community | 4 |
| `Get_summary → Fetch_news_sentiment` | intra_community | 4 |
| `Run_benchmark → Warning` | cross_community | 4 |
| `Run_diagnostic → Fetch_news_sentiment` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tools | 6 calls |
| Unit | 5 calls |
| Services | 4 calls |
| Execution | 3 calls |
| App | 2 calls |
| Cluster_1 | 1 calls |
| Scripts | 1 calls |

## How to Explore

1. `gitnexus_context({name: "list_all"})` — see callers and callees
2. `gitnexus_query({query: "logic"})` — find related execution flows
3. Read key files listed above for implementation details
