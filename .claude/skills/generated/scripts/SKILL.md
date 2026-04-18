---
name: scripts
description: "Skill for the Scripts area of Advanced_Btc_Bot. 91 symbols across 9 files."
---

# Scripts

91 symbols | 9 files | Cohesion: 82%

## When to Use

- Working with code in `MiroFish/`
- Understanding how disable_oasis_logging, init_logging_for_simulation, update_status work
- Modifying scripts-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `MiroFish/backend/scripts/run_parallel_simulation.py` | disable_oasis_logging, init_logging_for_simulation, ParallelIPCHandler, update_status, load_config (+19) |
| `MiroFish/backend/scripts/action_logger.py` | PlatformActionLogger, SimulationLogManager, get_twitter_logger, get_reddit_logger, log (+16) |
| `MiroFish/backend/scripts/run_twitter_simulation.py` | IPCHandler, update_status, _get_profile_path, _get_db_path, _create_model (+14) |
| `MiroFish/backend/scripts/run_reddit_simulation.py` | IPCHandler, update_status, _get_profile_path, _get_db_path, _create_model (+14) |
| `scripts/train_model.py` | parse_args, main |
| `logic/ml_brain.py` | create_labels, get_first_hit |
| `scripts/download_data.py` | fetch_historical_data, main |
| `multicore_master_bot.py` | format_quantity_async |
| `tests/unit/test_tier2_ml.py` | mock_ml_data |

## Entry Points

Start here when exploring this area:

- **`disable_oasis_logging`** (Function) — `MiroFish/backend/scripts/run_parallel_simulation.py:120`
- **`init_logging_for_simulation`** (Function) — `MiroFish/backend/scripts/run_parallel_simulation.py:141`
- **`update_status`** (Function) — `MiroFish/backend/scripts/run_parallel_simulation.py:246`
- **`load_config`** (Function) — `MiroFish/backend/scripts/run_parallel_simulation.py:604`
- **`main`** (Function) — `MiroFish/backend/scripts/run_parallel_simulation.py:1461`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ParallelIPCHandler` | Class | `MiroFish/backend/scripts/run_parallel_simulation.py` | 217 |
| `PlatformActionLogger` | Class | `MiroFish/backend/scripts/action_logger.py` | 22 |
| `SimulationLogManager` | Class | `MiroFish/backend/scripts/action_logger.py` | 119 |
| `IPCHandler` | Class | `MiroFish/backend/scripts/run_twitter_simulation.py` | 146 |
| `IPCHandler` | Class | `MiroFish/backend/scripts/run_reddit_simulation.py` | 146 |
| `PlatformSimulation` | Class | `MiroFish/backend/scripts/run_parallel_simulation.py` | 1062 |
| `UnicodeFormatter` | Class | `MiroFish/backend/scripts/run_twitter_simulation.py` | 53 |
| `TwitterSimulationRunner` | Class | `MiroFish/backend/scripts/run_twitter_simulation.py` | 385 |
| `UnicodeFormatter` | Class | `MiroFish/backend/scripts/run_reddit_simulation.py` | 53 |
| `RedditSimulationRunner` | Class | `MiroFish/backend/scripts/run_reddit_simulation.py` | 385 |
| `ActionLogger` | Class | `MiroFish/backend/scripts/action_logger.py` | 201 |
| `disable_oasis_logging` | Function | `MiroFish/backend/scripts/run_parallel_simulation.py` | 120 |
| `init_logging_for_simulation` | Function | `MiroFish/backend/scripts/run_parallel_simulation.py` | 141 |
| `update_status` | Function | `MiroFish/backend/scripts/run_parallel_simulation.py` | 246 |
| `load_config` | Function | `MiroFish/backend/scripts/run_parallel_simulation.py` | 604 |
| `main` | Function | `MiroFish/backend/scripts/run_parallel_simulation.py` | 1461 |
| `get_twitter_logger` | Function | `MiroFish/backend/scripts/action_logger.py` | 169 |
| `get_reddit_logger` | Function | `MiroFish/backend/scripts/action_logger.py` | 175 |
| `poll_command` | Function | `MiroFish/backend/scripts/run_parallel_simulation.py` | 256 |
| `send_response` | Function | `MiroFish/backend/scripts/run_parallel_simulation.py` | 279 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Analyze_frequency → Get_first_hit` | cross_community | 4 |
| `Process_commands → _get_env_and_graph` | intra_community | 4 |
| `Process_commands → _get_interview_result` | intra_community | 4 |
| `Main → Disable_oasis_logging` | intra_community | 3 |
| `Main → Get_first_hit` | intra_community | 3 |
| `Main → UnicodeFormatter` | intra_community | 3 |
| `Main → _create_model` | cross_community | 3 |
| `Main → _get_profile_path` | cross_community | 3 |
| `Main → _get_db_path` | cross_community | 3 |
| `Main → IPCHandler` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tools | 1 calls |
| Logic | 1 calls |

## How to Explore

1. `gitnexus_context({name: "disable_oasis_logging"})` — see callers and callees
2. `gitnexus_query({query: "scripts"})` — find related execution flows
3. Read key files listed above for implementation details
