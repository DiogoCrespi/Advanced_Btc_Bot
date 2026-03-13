from data_engine import DataEngine
import requests

engine = DataEngine()
# 1. List Discovery
contracts = engine.fetch_delivery_contracts(asset="BTC")
print("\n--- BTC Quarterly Contracts Found ---")
for c in contracts:
    print(f"Symbol: {c['symbol']} | Expiry Type: {c['contractType']}")

# 2. Get Real-time yields
print("\n--- Real-time Yield Scan ---")
from basis_logic import BasisLogic
logic = BasisLogic()

results = []
for c in contracts:
    symbol = c['symbol']
    # Pegar preços
    data = engine.fetch_basis_data(spot_symbol="BTCUSDT", delivery_symbol=symbol)
    if data:
        expiry = logic.parse_expiry(symbol)
        y = logic.calculate_annualized_yield(data['spot'], data['future'], expiry)
        print(f"Contract: {symbol} | Spot: {data['spot']} | Future: {data['future']} | Annualized Yield: {y*100:.2f}%")
        results.append({**data, 'symbol': symbol, 'yield': y})

best = logic.get_best_contract(results)
if best:
    print(f"\nBest Opportunity: {best['symbol']} with {best['annualized_yield']*100:.2f}% Yield!")
