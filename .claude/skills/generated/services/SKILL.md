---
name: services
description: "Skill for the Services area of Advanced_Btc_Bot. 338 symbols across 22 files."
---

# Services

338 symbols | 22 files | Cohesion: 64%

## When to Use

- Working with code in `MiroFish/`
- Understanding how close, to_dict, to_dict work
- Modifying services-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `MiroFish/backend/app/services/report_agent.py` | ReportLogger, ReportConsoleLogger, close, __del__, to_dict (+64) |
| `MiroFish/backend/app/services/zep_tools.py` | __init__, _call_with_retry, get_node_detail, safe_get_detail, NodeInfo (+30) |
| `MiroFish/backend/app/services/simulation_runner.py` | check_env_alive, get_env_status_detail, interview_agent, interview_agents_batch, interview_all_agents (+26) |
| `MiroFish/backend/app/api/simulation.py` | get_simulation_profiles_realtime, get_simulation_config_realtime, optimize_interview_prompt, interview_agent, interview_agents_batch (+23) |
| `MiroFish/backend/app/services/oasis_profile_generator.py` | __init__, _is_individual_entity, _generate_profile_with_llm, _fix_truncated_json, _try_fix_json (+21) |
| `MiroFish/backend/app/services/simulation_config_generator.py` | TimeSimulationConfig, EventConfig, PlatformConfig, SimulationParameters, to_dict (+18) |
| `MiroFish/backend/app/services/simulation_ipc.py` | CommandType, from_dict, poll_commands, CommandStatus, IPCCommand (+16) |
| `MiroFish/backend/app/services/zep_graph_memory_updater.py` | ZepGraphMemoryUpdater, __init__, start, stop, create_updater (+13) |
| `MiroFish/backend/app/api/report.py` | download_report, delete_report, get_report_progress, get_report_sections, get_single_section (+11) |
| `MiroFish/backend/app/services/simulation_manager.py` | prepare_simulation, profile_progress, SimulationStatus, _get_simulation_dir, _load_simulation_state (+7) |

## Entry Points

Start here when exploring this area:

- **`close`** (Function) — `MiroFish/backend/app/services/report_agent.py:365`
- **`to_dict`** (Function) — `MiroFish/backend/app/services/report_agent.py:424`
- **`to_dict`** (Function) — `MiroFish/backend/app/services/report_agent.py:454`
- **`generate_report`** (Function) — `MiroFish/backend/app/services/report_agent.py:1532`
- **`save_outline`** (Function) — `MiroFish/backend/app/services/report_agent.py:2080`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ReportLogger` | Class | `MiroFish/backend/app/services/report_agent.py` | 35 |
| `ReportConsoleLogger` | Class | `MiroFish/backend/app/services/report_agent.py` | 306 |
| `ZepGraphMemoryUpdater` | Class | `MiroFish/backend/app/services/zep_graph_memory_updater.py` | 201 |
| `TimeSimulationConfig` | Class | `MiroFish/backend/app/services/simulation_config_generator.py` | 83 |
| `EventConfig` | Class | `MiroFish/backend/app/services/simulation_config_generator.py` | 113 |
| `PlatformConfig` | Class | `MiroFish/backend/app/services/simulation_config_generator.py` | 129 |
| `SimulationParameters` | Class | `MiroFish/backend/app/services/simulation_config_generator.py` | 146 |
| `SimulationConfigGenerator` | Class | `MiroFish/backend/app/services/simulation_config_generator.py` | 199 |
| `EntityNode` | Class | `MiroFish/backend/app/services/zep_entity_reader.py` | 23 |
| `FilteredEntities` | Class | `MiroFish/backend/app/services/zep_entity_reader.py` | 55 |
| `CommandType` | Class | `MiroFish/backend/app/services/simulation_ipc.py` | 25 |
| `GraphInfo` | Class | `MiroFish/backend/app/services/graph_builder.py` | 23 |
| `CommandStatus` | Class | `MiroFish/backend/app/services/simulation_ipc.py` | 32 |
| `IPCCommand` | Class | `MiroFish/backend/app/services/simulation_ipc.py` | 41 |
| `SimulationIPCClient` | Class | `MiroFish/backend/app/services/simulation_ipc.py` | 95 |
| `RunnerStatus` | Class | `MiroFish/backend/app/services/simulation_runner.py` | 35 |
| `SimulationRunState` | Class | `MiroFish/backend/app/services/simulation_runner.py` | 101 |
| `AgentActivityConfig` | Class | `MiroFish/backend/app/services/simulation_config_generator.py` | 51 |
| `NodeInfo` | Class | `MiroFish/backend/app/services/zep_tools.py` | 57 |
| `EdgeInfo` | Class | `MiroFish/backend/app/services/zep_tools.py` | 81 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Get_entities_by_type → Warning` | cross_community | 7 |
| `Get_entities_by_type → Error` | cross_community | 7 |
| `Interview_all_agents → CommandStatus` | intra_community | 7 |
| `Cleanup_handler → To_episode_text` | cross_community | 7 |
| `Cleanup_handler → _get_platform_display_name` | cross_community | 7 |
| `Get_graph_entities → Warning` | cross_community | 6 |
| `Get_graph_entities → Error` | cross_community | 6 |
| `Close_simulation_env → CommandStatus` | cross_community | 6 |
| `Get_entity_detail → Warning` | cross_community | 6 |
| `Get_entity_detail → Error` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Api | 11 calls |
| Models | 9 calls |
| App | 8 calls |

## How to Explore

1. `gitnexus_context({name: "close"})` — see callers and callees
2. `gitnexus_query({query: "services"})` — find related execution flows
3. Read key files listed above for implementation details
