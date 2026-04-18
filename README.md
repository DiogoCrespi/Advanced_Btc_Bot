# Advanced Multicore BTC Bot

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)

**Modular ML-Driven Trading Bot with Async Execution**

The Advanced Multicore BTC Bot is an institutional-grade, high-performance algorithmic trading system designed for concurrency and predictive precision. By integrating advanced Machine Learning (Random Forest) with order-flow analysis and a local LLM-based sentiment oracle, it executes data-driven strategies seamlessly across multiple concurrent processes. Built entirely on asynchronous architecture (asyncio) and ProcessPools, this engine prevents UI and I/O blocking, ensuring absolute responsiveness in volatile markets.

## 🏗 Architecture Overview

The system operates strictly on a three-tier concurrent architecture to isolate functionality and optimize performance:

1. **Data Pipeline (`data/data_engine.py`)**:
   The ingestion layer. It asynchronously fetches, normalizes, and cleans high-frequency data (OHLCV, Order Flow CVD, Macro S&P/DXY, and Funding Rates) from the Binance and other APIs, maintaining in-memory caches to eliminate redundant I/O requests.

2. **ML Predictor Engine (`logic/ml_brain.py`)**:
   The analytical core. Offloaded to a separate CPU process via `ProcessPoolExecutor`, the Machine Learning Brain trains and scores predictive Random Forest models using advanced feature engineering (Triple Barrier Method labeling, Momentum, Volatility) to emit directional trading signals (Alpha).

3. **Execution Engine (`multicore_master_bot.py`)**:
   The async orchestrator. Utilizing an event-driven loop (`asyncio`), it intercepts signals from the ML Predictor, evaluates risk thresholds (Risk Manager), queries the **LocalOracle** (LLM-based sentiment) for macro context, and dispatches execution orders (Spot and Basis Arbitrage) without blocking main operations.

## 🚀 Quick Start

Ensure Docker is installed, then launch the entire bot cluster in **Demo Mode** (Paper Trading) with a single command:

```bash
docker compose up -d --build
```

Monitor operations natively via terminal:
```bash
docker compose logs -f btc-master-bot
```

*Note: The bot starts in Demo Mode by default, writing paper PnL to `results/bot_status.json` and `results/balance_state.txt`. Ensure your `.env` is populated with `BINANCE_API_KEY` for read-only market access.*

## 🗺 Project Roadmap

We are continuously evolving the engine for better performance and modularity. Here is what is next:
- **Phase 1: Sentiment Analysis Enhancements** - Deeper integration with LocalOracle for real-time NLP scoring using local LLMs (Ollama) and high-performance APIs (Groq).
- **Phase 2: Web Dashboard** - A full-stack React dashboard to visualize ML feature importance, equity curves, and active trades in real-time.
- **Phase 3: Backtesting CLI** - An isolated, optimized historical backtesting sandbox using vector-based Pandas operations to simulate multi-year strategies in seconds.
- **Phase 4: Multi-Exchange Arbitrage** - Native support for Bybit and OKX orderbook ingestion.

## 🤝 Open-Source Contribution Guidelines

We demand high standards for performance and code cleanliness. We welcome contributions that align with our core focus: Scalability, Precision, and Asynchronous execution.

1. **Pull Request Workflow**:
   Fork the repository, create a descriptive branch (e.g., `feature/ml-hyperopt` or `fix/async-lock`), and submit a Pull Request. Ensure all existing tests pass locally before submission.
2. **Issue Reporting**:
   Use the GitHub Issue tracker. Include traceback logs, Python version, Docker configuration, and steps to reproduce.
3. **Code Style**:
   Strict adherence to PEP-8 formatting. Code must be explicitly typed where possible. Comments and logs must be written without accents (e.g., `nao` instead of `não`) to maintain cross-platform encoding compatibility.
4. **Modular Design**:
   The bot is strictly decoupled. If adding a new trading strategy, create a distinct module in `logic/` (e.g., `logic/new_strategy.py`) and inject it into the `IntelligenceManager` or `multicore_master_bot.py`. **Never** block the main event loop (`asyncio.sleep` instead of `time.sleep`).

## ⚠️ Strict Financial Disclaimer

**RISK WARNING:** Trading cryptocurrencies involves significant risk and can result in the loss of your invested capital. This software is provided for educational and research purposes only. The authors, contributors, and maintainers of this project are **not** registered financial advisors.

Past performance of any trading system or ML model is not indicative of future results. You are solely responsible for all trades executed by this bot. By using this software, you agree that you understand the risks and will not hold the developers liable for any financial losses. Never trade with money you cannot afford to lose.
