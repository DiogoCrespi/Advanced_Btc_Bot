import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
import os

class PerformanceAnalyzer:
    def __init__(self, trade_history: List[Dict[str, Any]], initial_capital: float = 1000.0) -> None:
        self.trade_history = trade_history
        self.initial_capital = initial_capital
        self.trades_df = pd.DataFrame(trade_history)
        if not self.trades_df.empty:
            self.trades_df['timestamp'] = pd.to_datetime(self.trades_df['timestamp'])
            self.trades_df.set_index('timestamp', inplace=True)

    def _pair_trades(self) -> pd.DataFrame:
        """
        Pairs BUY and SELL orders to calculate individual trade profitability.
        Simplistic FIFO pairing.
        """
        if self.trades_df.empty:
            return pd.DataFrame()

        paired_trades = []
        open_positions = {} # {symbol: list of buys}

        for idx, row in self.trades_df.iterrows():
            sym = row['symbol']
            if row['side'] == 'BUY':
                if sym not in open_positions:
                    open_positions[sym] = []
                open_positions[sym].append({'price': row['price'], 'qty': row['quantity'], 'time': idx})
            elif row['side'] == 'SELL' and sym in open_positions and open_positions[sym]:
                # Pair with oldest BUY (FIFO)
                buy = open_positions[sym].pop(0)
                # Calculate PnL
                cost_basis = buy['price'] * row['quantity'] # Assume selling the exact qty
                revenue = row['price'] * row['quantity']
                pnl = revenue - cost_basis
                pnl_pct = (row['price'] / buy['price']) - 1

                paired_trades.append({
                    'entry_time': buy['time'],
                    'exit_time': idx,
                    'symbol': sym,
                    'entry_price': buy['price'],
                    'exit_price': row['price'],
                    'qty': row['quantity'],
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'duration': (idx - buy['time']).total_seconds()
                })

        return pd.DataFrame(paired_trades)

    def calculate_metrics(self) -> Dict[str, float]:
        if self.trades_df.empty:
            return {
                "Total Trades": 0,
                "Net Profit": 0.0,
                "ROI (%)": 0.0,
                "Win Rate (%)": 0.0,
                "Profit Factor": 0.0,
                "Max Drawdown (%)": 0.0,
                "Sharpe Ratio": 0.0,
                "Sortino Ratio": 0.0
            }

        paired_df = self._pair_trades()
        if paired_df.empty:
            return {
                "Total Trades": len(self.trades_df),
                "Net Profit": 0.0,
                "ROI (%)": 0.0,
                "Win Rate (%)": 0.0,
                "Profit Factor": 0.0,
                "Max Drawdown (%)": 0.0,
                "Sharpe Ratio": 0.0,
                "Sortino Ratio": 0.0
            }

        total_trades = len(paired_df)
        winning_trades = paired_df[paired_df['pnl'] > 0]
        losing_trades = paired_df[paired_df['pnl'] <= 0]

        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0

        gross_profit = winning_trades['pnl'].sum()
        gross_loss = abs(losing_trades['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        net_profit = gross_profit - gross_loss
        roi = (net_profit / self.initial_capital) * 100

        # Create Equity Curve to calculate Drawdown and Ratios
        paired_df.sort_values('exit_time', inplace=True)
        paired_df['equity'] = self.initial_capital + paired_df['pnl'].cumsum()

        paired_df['peak'] = paired_df['equity'].cummax()
        paired_df['drawdown'] = (paired_df['peak'] - paired_df['equity']) / paired_df['peak']
        max_drawdown = paired_df['drawdown'].max() * 100

        # Ratios (simplified, assuming daily risk-free rate of 0)
        returns = paired_df['pnl_pct']
        if len(returns) > 1 and returns.std() != 0:
            sharpe_ratio = np.sqrt(len(returns)) * (returns.mean() / returns.std())

            negative_returns = returns[returns < 0]
            if len(negative_returns) > 0 and negative_returns.std() != 0:
                sortino_ratio = np.sqrt(len(returns)) * (returns.mean() / negative_returns.std())
            else:
                sortino_ratio = float('inf')
        else:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0

        return {
            "Total Trades": total_trades,
            "Net Profit": float(net_profit),
            "ROI (%)": float(roi),
            "Win Rate (%)": float(win_rate * 100),
            "Profit Factor": float(profit_factor),
            "Max Drawdown (%)": float(max_drawdown),
            "Sharpe Ratio": float(sharpe_ratio),
            "Sortino Ratio": float(sortino_ratio)
        }

    def generate_equity_curve(self, output_path: str = "results/equity_curve.csv") -> None:
        """
        Saves the equity curve to a CSV file.
        """
        if self.trades_df.empty:
            print("No trades to generate equity curve.")
            return

        paired_df = self._pair_trades()
        if paired_df.empty:
            print("No completed trades to generate equity curve.")
            return

        paired_df.sort_values('exit_time', inplace=True)
        paired_df['equity'] = self.initial_capital + paired_df['pnl'].cumsum()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        paired_df[['exit_time', 'equity', 'pnl']].to_csv(output_path, index=False)
        print(f"Equity curve saved to {output_path}")

    def print_summary(self) -> None:
        print("\n" + "="*40)
        print("📊 BACKTEST PERFORMANCE SUMMARY")
        print("="*40)
        metrics = self.calculate_metrics()
        for k, v in metrics.items():
            if "Ratio" in k or "Factor" in k:
                print(f"{k:20}: {v:.2f}")
            elif "Trades" in k:
                print(f"{k:20}: {int(v)}")
            else:
                print(f"{k:20}: {v:+.2f}")
        print("="*40 + "\n")
