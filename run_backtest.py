import os
import pandas as pd
from datetime import datetime, timedelta
from logic.execution import BacktestEngine, PerformanceAnalyzer

def generate_mock_data() -> pd.DataFrame:
    """Generates simple mock OHLCV data for testing."""
    dates = pd.date_range(end=datetime.now(), periods=100, freq='1h')

    # Create a simple trend for testing
    closes = [100.0]
    for _ in range(1, 100):
        # Slightly upward trend with noise
        closes.append(closes[-1] * (1 + 0.005))

    df = pd.DataFrame({
        'open': closes,
        'high': [c * 1.01 for c in closes],
        'low': [c * 0.99 for c in closes],
        'close': closes,
        'volume': [1000] * 100
    }, index=dates)

    return df

def run_backtest_example():
    print("Initializing Backtest Environment...")

    # 1. Initialize Engine
    engine = BacktestEngine(initial_balance=10000.0, maker_fee=0.001, taker_fee=0.001)

    # 2. Load Data
    df = generate_mock_data()
    engine.load_data(df)

    print(f"Loaded {len(df)} rows of data.")
    print(f"Initial Balance: BRL {engine.get_balance('BRL')}")

    # 3. Simulation Loop
    step_count = 0
    while engine.step():
        step_count += 1
        current_idx = engine.current_index
        current_price = df.iloc[current_idx]['close']

        # Simple Mock Strategy:
        # Buy on step 10, Sell on step 50
        # Buy on step 60, Sell on step 90

        if step_count == 10:
            qty = (engine.get_balance('BRL') * 0.5) / current_price # 50% of balance
            print(f"Step {step_count}: Buying {qty:.4f} BTC at {current_price:.2f}")
            engine.create_order(symbol="BTCBRL", side="BUY", order_type="MARKET", quantity=qty)

        elif step_count == 50:
            qty = engine.get_balance('BTC')
            if qty > 0:
                print(f"Step {step_count}: Selling {qty:.4f} BTC at {current_price:.2f}")
                engine.create_order(symbol="BTCBRL", side="SELL", order_type="MARKET", quantity=qty)

        elif step_count == 60:
            qty = (engine.get_balance('BRL') * 0.5) / current_price
            print(f"Step {step_count}: Buying {qty:.4f} BTC at {current_price:.2f}")
            engine.create_order(symbol="BTCBRL", side="BUY", order_type="MARKET", quantity=qty)

        elif step_count == 90:
            qty = engine.get_balance('BTC')
            if qty > 0:
                print(f"Step {step_count}: Selling {qty:.4f} BTC at {current_price:.2f}")
                engine.create_order(symbol="BTCBRL", side="SELL", order_type="MARKET", quantity=qty)

    print("\nSimulation Complete.")
    print(f"Final Balance: BRL {engine.get_balance('BRL'):.2f}")
    print(f"Final BTC Balance: {engine.get_balance('BTC'):.6f}")

    # 4. Performance Analysis
    print("\nAnalyzing Performance...")
    analyzer = PerformanceAnalyzer(engine.trade_history, initial_capital=10000.0)
    analyzer.print_summary()

    os.makedirs('results', exist_ok=True)
    analyzer.generate_equity_curve('results/backtest_example_equity.csv')

if __name__ == "__main__":
    run_backtest_example()
