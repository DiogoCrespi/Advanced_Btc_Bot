---
name: cluster-1
description: "Skill for the Cluster_1 area of Advanced_Btc_Bot. 6 symbols across 1 files."
---

# Cluster_1

6 symbols | 1 files | Cohesion: 77%

## When to Use

- Understanding how start, main, WebSocketSupervisor work
- Modifying cluster_1-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `multicore_master_bot.py` | WebSocketSupervisor, start, _run_socket_session, _handle_reconnection, _train_initial_evo_pop (+1) |

## Entry Points

Start here when exploring this area:

- **`start`** (Function) — `multicore_master_bot.py:65`
- **`main`** (Function) — `multicore_master_bot.py:669`
- **`WebSocketSupervisor`** (Class) — `multicore_master_bot.py:58`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `WebSocketSupervisor` | Class | `multicore_master_bot.py` | 58 |
| `start` | Function | `multicore_master_bot.py` | 65 |
| `main` | Function | `multicore_master_bot.py` | 669 |
| `_run_socket_session` | Function | `multicore_master_bot.py` | 77 |
| `_handle_reconnection` | Function | `multicore_master_bot.py` | 109 |
| `_train_initial_evo_pop` | Function | `multicore_master_bot.py` | 443 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → Task` | cross_community | 3 |
| `Main → _run_socket_session` | intra_community | 3 |
| `Main → _handle_reconnection` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Models | 1 calls |
| Cluster_5 | 1 calls |

## How to Explore

1. `gitnexus_context({name: "start"})` — see callers and callees
2. `gitnexus_query({query: "cluster_1"})` — find related execution flows
3. Read key files listed above for implementation details
