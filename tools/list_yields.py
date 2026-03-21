from data_engine import DataEngine
from basis_logic import BasisLogic
import pandas as pd

def list_all():
    engine = DataEngine()
    logic = BasisLogic()
    contracts = engine.fetch_delivery_contracts(asset="BTC")
    
    results = []
    for c in contracts:
        symbol = c['symbol']
        data = engine.fetch_basis_data(spot_symbol="BTCBRL", delivery_symbol=symbol)
        if data:
            expiry = logic.parse_expiry(symbol)
            y = logic.calculate_annualized_yield(data['spot'], data['future'], expiry)
            results.append({
                'Symbol': symbol,
                'Expiry': expiry.strftime('%Y-%m-%d'),
                'Yield (%)': y * 100
            })
            
    df = pd.DataFrame(results)
    print("\n=== TODOS OS CONTRATOS BTC/BRL ===")
    print(df.sort_values(by='Expiry').to_string(index=False))
    print("==================================\n")

if __name__ == "__main__":
    list_all()
