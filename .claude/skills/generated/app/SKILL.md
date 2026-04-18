---
name: app
description: "Skill for the App area of Advanced_Btc_Bot. 13 symbols across 7 files."
---

# App

13 symbols | 7 files | Cohesion: 60%

## When to Use

- Working with code in `MiroFish/`
- Understanding how log_request, log_response, search_edges work
- Modifying app-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `MiroFish/backend/app/utils/logger.py` | get_logger, debug, _ensure_utf8_stdout, setup_logger |
| `MiroFish/backend/app/__init__.py` | log_request, log_response, create_app |
| `MiroFish/backend/app/services/oasis_profile_generator.py` | search_edges, search_nodes |
| `MiroFish/backend/app/api/simulation.py` | _check_simulation_prepared |
| `MiroFish/backend/run.py` | main |
| `MiroFish/backend/app/config.py` | validate |
| `MiroFish/backend/app/services/simulation_runner.py` | register_cleanup |

## Entry Points

Start here when exploring this area:

- **`log_request`** (Function) — `MiroFish/backend/app/__init__.py:54`
- **`log_response`** (Function) — `MiroFish/backend/app/__init__.py:61`
- **`search_edges`** (Function) — `MiroFish/backend/app/services/oasis_profile_generator.py:318`
- **`search_nodes`** (Function) — `MiroFish/backend/app/services/oasis_profile_generator.py:343`
- **`get_logger`** (Function) — `MiroFish/backend/app/utils/logger.py:91`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `log_request` | Function | `MiroFish/backend/app/__init__.py` | 54 |
| `log_response` | Function | `MiroFish/backend/app/__init__.py` | 61 |
| `search_edges` | Function | `MiroFish/backend/app/services/oasis_profile_generator.py` | 318 |
| `search_nodes` | Function | `MiroFish/backend/app/services/oasis_profile_generator.py` | 343 |
| `get_logger` | Function | `MiroFish/backend/app/utils/logger.py` | 91 |
| `debug` | Function | `MiroFish/backend/app/utils/logger.py` | 112 |
| `main` | Function | `MiroFish/backend/run.py` | 25 |
| `validate` | Function | `MiroFish/backend/app/config.py` | 79 |
| `create_app` | Function | `MiroFish/backend/app/__init__.py` | 19 |
| `register_cleanup` | Function | `MiroFish/backend/app/services/simulation_runner.py` | 1283 |
| `setup_logger` | Function | `MiroFish/backend/app/utils/logger.py` | 30 |
| `_check_simulation_prepared` | Function | `MiroFish/backend/app/api/simulation.py` | 244 |
| `_ensure_utf8_stdout` | Function | `MiroFish/backend/app/utils/logger.py` | 13 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Generate_single_profile → Debug` | cross_community | 5 |
| `Create_updater → Debug` | cross_community | 5 |
| `Stop_all → Debug` | cross_community | 5 |
| `Build_task → _ensure_utf8_stdout` | cross_community | 4 |
| `Get_sentiment_keywords → Debug` | cross_community | 4 |
| `Log_request → _ensure_utf8_stdout` | cross_community | 4 |
| `Log_response → _ensure_utf8_stdout` | cross_community | 4 |
| `Main → _ensure_utf8_stdout` | intra_community | 4 |
| `Main → Warning` | cross_community | 4 |
| `Start_simulation → Debug` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 4 calls |

## How to Explore

1. `gitnexus_context({name: "log_request"})` — see callers and callees
2. `gitnexus_query({query: "app"})` — find related execution flows
3. Read key files listed above for implementation details
