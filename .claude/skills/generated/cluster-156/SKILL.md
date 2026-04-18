---
name: cluster-156
description: "Skill for the Cluster_156 area of Advanced_Btc_Bot. 5 symbols across 1 files."
---

# Cluster_156

5 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `MiroFish/`
- Understanding how get_active_key, mark_as_exhausted, chat work
- Modifying cluster_156-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `MiroFish/backend/app/utils/llm_manager.py` | _save_state, get_active_key, mark_as_exhausted, chat, _format_messages_for_gemini |

## Entry Points

Start here when exploring this area:

- **`get_active_key`** (Function) — `MiroFish/backend/app/utils/llm_manager.py:66`
- **`mark_as_exhausted`** (Function) — `MiroFish/backend/app/utils/llm_manager.py:77`
- **`chat`** (Function) — `MiroFish/backend/app/utils/llm_manager.py:84`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `get_active_key` | Function | `MiroFish/backend/app/utils/llm_manager.py` | 66 |
| `mark_as_exhausted` | Function | `MiroFish/backend/app/utils/llm_manager.py` | 77 |
| `chat` | Function | `MiroFish/backend/app/utils/llm_manager.py` | 84 |
| `_save_state` | Function | `MiroFish/backend/app/utils/llm_manager.py` | 58 |
| `_format_messages_for_gemini` | Function | `MiroFish/backend/app/utils/llm_manager.py` | 127 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Chat → _save_state` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "get_active_key"})` — see callers and callees
2. `gitnexus_query({query: "cluster_156"})` — find related execution flows
3. Read key files listed above for implementation details
