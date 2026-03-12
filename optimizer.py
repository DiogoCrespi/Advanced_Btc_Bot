from backtest_full import FullBacktester
import itertools
import pandas as pd

def run_optimization():
    # Define Parameter Grid
    param_grid = {
        'entry_type': ['open', '25_ce', '50_ce'],
        'rr_ratio': [2.0, 3.0, 4.0],
        'ml_threshold': [0.0, 0.0005, 0.001],
        'use_smt': [True, False],
        'atr_sl': [True, False]
    }
    
    # Generate all combinations
    keys, values = zip(*param_grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    print(f"Starting Grid Search with {len(combinations)} combinations...")
    
    results = []
    backtester = FullBacktester(silent=True)
    backtester.prepare_data() # Explicitly prepare with new relaxed logic
    
    for i, params in enumerate(combinations):
        if i % 10 == 0:
            print(f"Processing combination {i}/{len(combinations)}...")
            
        # Run backtest with current params
        perf = backtester.run(**params)
        
        # Store results
        res = params.copy()
        res.update(perf)
        results.append(res)
    
    # Analyze results
    df = pd.DataFrame(results)
    df.sort_values(by='roi', ascending=False, inplace=True)
    
    print("\n--- TOP 10 CONFIGURATIONS ---")
    print(df.head(10).to_string(index=False))
    
    # Save to CSV
    df.to_csv('optimization_results.csv', index=False)
    print("\nResults saved to optimization_results.csv")
    
    best = df.iloc[0]
    print(f"\nBEST CONFIGURATION FOUND:")
    print(f"ROI: {best['roi']:.2f}% | Win Rate: {best['win_rate']:.2f}% | Trades: {best['total_trades']}")
    print(f"Parameters: Entry={best['entry_type']}, RR={best['rr_ratio']}, ML={best['ml_threshold']}, SMT={best['use_smt']}, ATR_SL={best['atr_sl']}")

if __name__ == "__main__":
    run_optimization()
