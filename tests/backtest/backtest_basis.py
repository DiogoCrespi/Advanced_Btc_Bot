from data_engine import DataEngine
from basis_logic import BasisLogic
from risk_manager import RiskManager
import pandas as pd
import numpy as np

class BasisBacktester:
    def __init__(self, initial_balance=10000):
        self.data_engine = DataEngine(period="180d", interval="1h")
        self.logic = BasisLogic(risk_free_rate_annual=0.10)
        self.risk = RiskManager(initial_balance=initial_balance)
        self.balance_usd = initial_balance
        self.active_position = None

    def run(self, spot_symbol="BTCUSDT", delivery_symbol="BTCUSD_260626"):
        print(f"Starting Basis Arbitrage backtest: Spot {spot_symbol} | Delivery {delivery_symbol}")
        
        # 1. Fetch Data
        df_spot = self.data_engine.fetch_data()[0]
        df_fut = self.data_engine.fetch_delivery_klines(symbol=delivery_symbol)
        
        if df_fut.empty:
            print("Failed to fetch delivery klines.")
            return

        # 2. Align Data (Remove Timezones)
        df_spot.index = df_spot.index.tz_localize(None).round('h')
        df_fut.index = df_fut.index.tz_localize(None).round('h')
        
        combined = df_spot[['Close']].join(df_fut[['close']], how='inner')
        combined.columns = ['Close_spot', 'Close_fut']
        print(f"Aligned rows: {len(combined)}")

        if combined.empty:
            print("No overlapping data found.")
            return

        expiry_date = self.logic.parse_expiry(delivery_symbol)
        
        # 3. Simulate Entry (At the start of the series)
        entry_price_spot = combined['Close_spot'].iloc[0]
        entry_price_fut = combined['Close_fut'].iloc[0]
        entry_time = combined.index[0]
        
        annual_yield = self.logic.calculate_annualized_yield(entry_price_spot, entry_price_fut, expiry_date)
        
        print(f"\n--- ENTRY LOG ---")
        print(f"Time: {entry_time}")
        print(f"Spot: ${entry_price_spot:.2f} | Future: ${entry_price_fut:.2f}")
        print(f"Locked Basis: ${(entry_price_fut - entry_price_spot):.2f}")
        print(f"Annualized Yield: {annual_yield*100:.2f}%")

        # 4. Holder Phase & Expiry
        # No Cash & Carry clássico, seguramos até o vencimento.
        # No vencimento: Future_Price == Spot_Price
        exit_price_spot = combined['Close_spot'].values[-1]
        exit_price_fut = combined['Close_fut'].values[-1]
        exit_time = combined.index[-1]
        
        # P&L Spot (Long): (Exit - Entry) / Entry
        spot_return = (exit_price_spot - entry_price_spot) / entry_price_spot
        
        # P&L Future (Short COIN-M Inverse): Qty_USD * (1/Entry - 1/Exit)
        # Assumimos alocação total
        qty_usd = self.balance_usd
        # PnL do short em BTC
        pnl_btc = self.risk.calculate_coin_m_pnl(entry_price_fut, exit_price_fut, qty_usd)
        
        # Resultado Final
        # Valor do Spot em BTC no final: (Entry_Value_USD * (1 + spot_return)) / Exit_Price_Spot
        # MAS, como o nosso colateral è o próprio BTC, o valor dele em USD acompanhou o mercado.
        final_balance_usd = self.balance_usd * (entry_price_fut / entry_price_spot)
        
        # Na verdade, a matemática simplificada do Cash e Carry:
        # Você ganha a diferença exata (o prêmio) que travou no começo.
        locked_profit_usd = (entry_price_fut - entry_price_spot) * (qty_usd / entry_price_spot)
        
        final_balance_audited = self.balance_usd + locked_profit_usd
        
        print(f"\n--- EXIT LOG (EXPIRY) ---")
        print(f"Time: {exit_time}")
        print(f"Spot: ${exit_price_spot:.2f} | Future: ${exit_price_fut:.2f}")
        print(f"Basis at Expiry: ${(exit_price_fut - exit_price_spot):.2f}")
        
        self.report(final_balance_audited)

    def report(self, final_balance):
        roi = ((final_balance - 10000) / 10000) * 100
        print(f"\n--- BASIS ARBITRAGE FINAL REPORT ---")
        print(f"Initial Balance: $10000.00")
        print(f"Final Balance:   ${final_balance:.2f}")
        print(f"Total ROI:       {roi:.2f}% (Locked Strategy)")

if __name__ == "__main__":
    tester = BasisBacktester()
    # Exemplo com um contato futuro que expira em Junho de 2026
    tester.run(delivery_symbol="BTCUSD_260626")
