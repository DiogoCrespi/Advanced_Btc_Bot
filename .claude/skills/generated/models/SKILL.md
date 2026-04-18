---
name: models
description: "Skill for the Models area of Advanced_Btc_Bot. 35 symbols across 6 files."
---

# Models

35 symbols | 6 files | Cohesion: 68%

## When to Use

- Working with code in `MiroFish/`
- Understanding how create_task, to_dict, from_dict work
- Modifying models-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `MiroFish/backend/app/models/project.py` | ProjectStatus, to_dict, from_dict, _get_project_meta_path, _get_project_text_path (+12) |
| `MiroFish/backend/app/api/graph.py` | get_project, reset_project, build_graph, list_projects, delete_project (+2) |
| `MiroFish/backend/app/models/task.py` | Task, create_task, to_dict, TaskManager, get_task (+1) |
| `MiroFish/backend/app/api/simulation.py` | prepare_simulation, get_prepare_status |
| `MiroFish/backend/app/api/report.py` | generate_report, get_generate_status |
| `MiroFish/backend/app/services/graph_builder.py` | __init__ |

## Entry Points

Start here when exploring this area:

- **`create_task`** (Function) — `MiroFish/backend/app/models/task.py:73`
- **`to_dict`** (Function) — `MiroFish/backend/app/models/project.py:55`
- **`from_dict`** (Function) — `MiroFish/backend/app/models/project.py:76`
- **`save_project`** (Function) — `MiroFish/backend/app/models/project.py:168`
- **`get_project`** (Function) — `MiroFish/backend/app/models/project.py:177`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `Task` | Class | `MiroFish/backend/app/models/task.py` | 23 |
| `ProjectStatus` | Class | `MiroFish/backend/app/models/project.py` | 17 |
| `Project` | Class | `MiroFish/backend/app/models/project.py` | 27 |
| `TaskManager` | Class | `MiroFish/backend/app/models/task.py` | 54 |
| `create_task` | Function | `MiroFish/backend/app/models/task.py` | 73 |
| `to_dict` | Function | `MiroFish/backend/app/models/project.py` | 55 |
| `from_dict` | Function | `MiroFish/backend/app/models/project.py` | 76 |
| `save_project` | Function | `MiroFish/backend/app/models/project.py` | 168 |
| `get_project` | Function | `MiroFish/backend/app/models/project.py` | 177 |
| `get_extracted_text` | Function | `MiroFish/backend/app/models/project.py` | 282 |
| `prepare_simulation` | Function | `MiroFish/backend/app/api/simulation.py` | 365 |
| `generate_report` | Function | `MiroFish/backend/app/api/report.py` | 27 |
| `get_project` | Function | `MiroFish/backend/app/api/graph.py` | 38 |
| `reset_project` | Function | `MiroFish/backend/app/api/graph.py` | 94 |
| `build_graph` | Function | `MiroFish/backend/app/api/graph.py` | 267 |
| `create_project` | Function | `MiroFish/backend/app/models/project.py` | 133 |
| `list_projects` | Function | `MiroFish/backend/app/models/project.py` | 198 |
| `delete_project` | Function | `MiroFish/backend/app/models/project.py` | 222 |
| `save_file_to_project` | Function | `MiroFish/backend/app/models/project.py` | 241 |
| `get_project_files` | Function | `MiroFish/backend/app/models/project.py` | 293 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Get_generate_status → _get_report_folder` | cross_community | 5 |
| `Generate_report → _get_report_folder` | cross_community | 5 |
| `List_projects → _get_project_dir` | cross_community | 5 |
| `List_projects → ProjectStatus` | cross_community | 5 |
| `Prepare_simulation → _get_simulation_dir` | cross_community | 4 |
| `Prepare_simulation → SimulationState` | cross_community | 4 |
| `Prepare_simulation → SimulationStatus` | cross_community | 4 |
| `Generate_ontology → _get_project_dir` | cross_community | 4 |
| `Build_graph → _get_project_dir` | cross_community | 4 |
| `Build_graph → ProjectStatus` | intra_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 15 calls |
| App | 4 calls |
| Api | 2 calls |

## How to Explore

1. `gitnexus_context({name: "create_task"})` — see callers and callees
2. `gitnexus_query({query: "models"})` — find related execution flows
3. Read key files listed above for implementation details
