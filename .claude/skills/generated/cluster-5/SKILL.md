---
name: cluster-5
description: "Skill for the Cluster_5 area of Advanced_Btc_Bot. 5 symbols across 1 files."
---

# Cluster_5

5 symbols | 1 files | Cohesion: 71%

## When to Use

- Understanding how notify_telegram, run_async, scan_asset work
- Modifying cluster_5-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `multicore_master_bot.py` | notify_telegram, _render_dashboard, _process_xaut, run_async, scan_asset |

## Entry Points

Start here when exploring this area:

- **`notify_telegram`** (Function) — `multicore_master_bot.py:270`
- **`run_async`** (Function) — `multicore_master_bot.py:459`
- **`scan_asset`** (Function) — `multicore_master_bot.py:505`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `notify_telegram` | Function | `multicore_master_bot.py` | 270 |
| `run_async` | Function | `multicore_master_bot.py` | 459 |
| `scan_asset` | Function | `multicore_master_bot.py` | 505 |
| `_render_dashboard` | Function | `multicore_master_bot.py` | 288 |
| `_process_xaut` | Function | `multicore_master_bot.py` | 408 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run_async → Async_log` | cross_community | 3 |
| `Run_async → Save_balance` | cross_community | 3 |
| `Run_async → Save_state` | cross_community | 3 |
| `Run_async → Notify_telegram` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Integration | 3 calls |

## How to Explore

1. `gitnexus_context({name: "notify_telegram"})` — see callers and callees
2. `gitnexus_query({query: "cluster_5"})` — find related execution flows
3. Read key files listed above for implementation details
