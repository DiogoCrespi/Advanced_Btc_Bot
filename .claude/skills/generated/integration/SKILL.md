---
name: integration
description: "Skill for the Integration area of Advanced_Btc_Bot. 8 symbols across 2 files."
---

# Integration

8 symbols | 2 files | Cohesion: 83%

## When to Use

- Working with code in `tests/`
- Understanding how async_log, save_balance, save_state work
- Modifying integration-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `multicore_master_bot.py` | async_log, save_balance, save_state, _process_usdt, MulticoreMasterBot |
| `tests/integration/test_paper_trading.py` | test_paper_trading_process_usdt, test_paper_trading_save_state, mock_bot |

## Entry Points

Start here when exploring this area:

- **`async_log`** (Function) — `multicore_master_bot.py:234`
- **`save_balance`** (Function) — `multicore_master_bot.py:235`
- **`save_state`** (Function) — `multicore_master_bot.py:255`
- **`test_paper_trading_process_usdt`** (Function) — `tests/integration/test_paper_trading.py:55`
- **`test_paper_trading_save_state`** (Function) — `tests/integration/test_paper_trading.py:68`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `MulticoreMasterBot` | Class | `multicore_master_bot.py` | 123 |
| `async_log` | Function | `multicore_master_bot.py` | 234 |
| `save_balance` | Function | `multicore_master_bot.py` | 235 |
| `save_state` | Function | `multicore_master_bot.py` | 255 |
| `test_paper_trading_process_usdt` | Function | `tests/integration/test_paper_trading.py` | 55 |
| `test_paper_trading_save_state` | Function | `tests/integration/test_paper_trading.py` | 68 |
| `mock_bot` | Function | `tests/integration/test_paper_trading.py` | 15 |
| `_process_usdt` | Function | `multicore_master_bot.py` | 386 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run_async → Async_log` | cross_community | 3 |
| `Run_async → Save_balance` | cross_community | 3 |
| `Run_async → Save_state` | cross_community | 3 |

## How to Explore

1. `gitnexus_context({name: "async_log"})` — see callers and callees
2. `gitnexus_query({query: "integration"})` — find related execution flows
3. Read key files listed above for implementation details
