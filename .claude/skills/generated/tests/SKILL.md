---
name: tests
description: "Skill for the Tests area of Advanced_Btc_Bot. 3 symbols across 1 files."
---

# Tests

3 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `tests/`
- Understanding how split_quoted, get_f90flags, test_get_f90flags work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tests/test_f90flags.py` | split_quoted, get_f90flags, test_get_f90flags |

## Entry Points

Start here when exploring this area:

- **`split_quoted`** (Function) — `tests/test_f90flags.py:4`
- **`get_f90flags`** (Function) — `tests/test_f90flags.py:8`
- **`test_get_f90flags`** (Function) — `tests/test_f90flags.py:22`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `split_quoted` | Function | `tests/test_f90flags.py` | 4 |
| `get_f90flags` | Function | `tests/test_f90flags.py` | 8 |
| `test_get_f90flags` | Function | `tests/test_f90flags.py` | 22 |

## How to Explore

1. `gitnexus_context({name: "split_quoted"})` — see callers and callees
2. `gitnexus_query({query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
