---
name: benchmarks
description: "Skill for the Benchmarks area of Advanced_Btc_Bot. 19 symbols across 3 files."
---

# Benchmarks

19 symbols | 3 files | Cohesion: 100%

## When to Use

- Working with code in `tests/`
- Understanding how mock_get, mock_post, get work
- Modifying benchmarks-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tests/benchmarks/benchmark_news.py` | MockResponse, mock_get, mock_post, get, post (+6) |
| `tests/benchmarks/benchmark_n1_isolated.py` | _get_user_name, _get_post_info, _get_comment_info, _enrich_action_context, fetch_new_actions_from_db |
| `tests/benchmarks/benchmark_n1_isolated_v2.py` | chunked_in_query, fetch_new_actions_from_db_optimized, resolve_author_name |

## Entry Points

Start here when exploring this area:

- **`mock_get`** (Function) — `tests/benchmarks/benchmark_news.py:23`
- **`mock_post`** (Function) — `tests/benchmarks/benchmark_news.py:27`
- **`get`** (Function) — `tests/benchmarks/benchmark_news.py:46`
- **`post`** (Function) — `tests/benchmarks/benchmark_news.py:49`
- **`async_mock_get`** (Function) — `tests/benchmarks/benchmark_news.py:58`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `MockResponse` | Class | `tests/benchmarks/benchmark_news.py` | 5 |
| `Ctx` | Class | `tests/benchmarks/benchmark_news.py` | 90 |
| `mock_get` | Function | `tests/benchmarks/benchmark_news.py` | 23 |
| `mock_post` | Function | `tests/benchmarks/benchmark_news.py` | 27 |
| `get` | Function | `tests/benchmarks/benchmark_news.py` | 46 |
| `post` | Function | `tests/benchmarks/benchmark_news.py` | 49 |
| `async_mock_get` | Function | `tests/benchmarks/benchmark_news.py` | 58 |
| `async_mock_post` | Function | `tests/benchmarks/benchmark_news.py` | 62 |
| `fetch_new_actions_from_db` | Function | `tests/benchmarks/benchmark_n1_isolated.py` | 214 |
| `get` | Function | `tests/benchmarks/benchmark_news.py` | 89 |
| `post` | Function | `tests/benchmarks/benchmark_news.py` | 98 |
| `chunked_in_query` | Function | `tests/benchmarks/benchmark_n1_isolated_v2.py` | 29 |
| `fetch_new_actions_from_db_optimized` | Function | `tests/benchmarks/benchmark_n1_isolated_v2.py` | 39 |
| `resolve_author_name` | Function | `tests/benchmarks/benchmark_n1_isolated_v2.py` | 189 |
| `__aenter__` | Function | `tests/benchmarks/benchmark_news.py` | 91 |
| `_get_user_name` | Function | `tests/benchmarks/benchmark_n1_isolated.py` | 29 |
| `_get_post_info` | Function | `tests/benchmarks/benchmark_n1_isolated.py` | 63 |
| `_get_comment_info` | Function | `tests/benchmarks/benchmark_n1_isolated.py` | 93 |
| `_enrich_action_context` | Function | `tests/benchmarks/benchmark_n1_isolated.py` | 123 |

## How to Explore

1. `gitnexus_context({name: "mock_get"})` — see callers and callees
2. `gitnexus_query({query: "benchmarks"})` — find related execution flows
3. Read key files listed above for implementation details
