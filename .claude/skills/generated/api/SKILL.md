---
name: api
description: "Skill for the Api area of Advanced_Btc_Bot. 17 symbols across 6 files."
---

# Api

17 symbols | 6 files | Cohesion: 63%

## When to Use

- Working with code in `MiroFish/`
- Understanding how to_simple_dict, update_task, complete_task work
- Modifying api-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `MiroFish/backend/app/api/simulation.py` | run_prepare, list_simulations, _get_report_id_for_simulation, get_simulation_history, get_simulation_config |
| `MiroFish/backend/app/services/simulation_manager.py` | to_simple_dict, SimulationManager, list_simulations, get_simulation_config |
| `MiroFish/backend/app/models/task.py` | update_task, complete_task, fail_task |
| `MiroFish/backend/app/api/report.py` | run_generate, progress_callback |
| `MiroFish/backend/app/api/graph.py` | add_progress_callback, wait_progress_callback |
| `MiroFish/backend/app/services/report_agent.py` | ReportAgent |

## Entry Points

Start here when exploring this area:

- **`to_simple_dict`** (Function) — `MiroFish/backend/app/services/simulation_manager.py:99`
- **`update_task`** (Function) — `MiroFish/backend/app/models/task.py:106`
- **`complete_task`** (Function) — `MiroFish/backend/app/models/task.py:145`
- **`fail_task`** (Function) — `MiroFish/backend/app/models/task.py:155`
- **`run_prepare`** (Function) — `MiroFish/backend/app/api/simulation.py:510`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ReportAgent` | Class | `MiroFish/backend/app/services/report_agent.py` | 864 |
| `SimulationManager` | Class | `MiroFish/backend/app/services/simulation_manager.py` | 114 |
| `to_simple_dict` | Function | `MiroFish/backend/app/services/simulation_manager.py` | 99 |
| `update_task` | Function | `MiroFish/backend/app/models/task.py` | 106 |
| `complete_task` | Function | `MiroFish/backend/app/models/task.py` | 145 |
| `fail_task` | Function | `MiroFish/backend/app/models/task.py` | 155 |
| `run_prepare` | Function | `MiroFish/backend/app/api/simulation.py` | 510 |
| `run_generate` | Function | `MiroFish/backend/app/api/report.py` | 126 |
| `progress_callback` | Function | `MiroFish/backend/app/api/report.py` | 143 |
| `add_progress_callback` | Function | `MiroFish/backend/app/api/graph.py` | 428 |
| `wait_progress_callback` | Function | `MiroFish/backend/app/api/graph.py` | 456 |
| `list_simulations` | Function | `MiroFish/backend/app/services/simulation_manager.py` | 462 |
| `get_simulation_config` | Function | `MiroFish/backend/app/services/simulation_manager.py` | 495 |
| `list_simulations` | Function | `MiroFish/backend/app/api/simulation.py` | 793 |
| `get_simulation_history` | Function | `MiroFish/backend/app/api/simulation.py` | 882 |
| `get_simulation_config` | Function | `MiroFish/backend/app/api/simulation.py` | 1268 |
| `_get_report_id_for_simulation` | Function | `MiroFish/backend/app/api/simulation.py` | 821 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run_generate → _get_elapsed_time` | cross_community | 5 |
| `Run_generate → _get_report_folder` | cross_community | 5 |
| `Get_simulation_history → _get_simulation_dir` | cross_community | 4 |
| `Get_simulation_history → SimulationState` | cross_community | 4 |
| `Get_simulation_history → SimulationStatus` | cross_community | 4 |
| `Get_simulation_history → SimulationRunState` | cross_community | 4 |
| `Get_simulation_history → RunnerStatus` | cross_community | 4 |
| `Get_simulation_history → AgentAction` | cross_community | 4 |
| `Run_generate → To_dict` | cross_community | 4 |
| `Run_generate → Info` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 13 calls |
| Models | 1 calls |

## How to Explore

1. `gitnexus_context({name: "to_simple_dict"})` — see callers and callees
2. `gitnexus_query({query: "api"})` — find related execution flows
3. Read key files listed above for implementation details
