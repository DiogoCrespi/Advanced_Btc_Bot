from data_engine import DataEngine
from basis_logic import BasisLogic
from risk_manager import RiskManager
import os
import time
from datetime import datetime
import json
import threading
from fastapi import FastAPI
import uvicorn

# FastAPI Instance
app = FastAPI()
# Shared state for API
shared_bot_state = {
    "status": "initializing",
    "strategy": "Basis Arbitrage COIN-M",
    "active_position": None,
    "last_update": None
}

@app.get("/api/v1/crypto-vault/status")
def get_status():
    return shared_bot_state

class BasisArbRealtime:
    def __init__(self, asset="BTC", threshold_annual_yield=0.08):
        self.asset = asset
        self.threshold = threshold_annual_yield
        self.engine = DataEngine()
        self.logic = BasisLogic()
        self.risk = RiskManager()
        
        self.state_file = "state.json"
        self.active_position = self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return None

    def save_state(self, state):
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

    def run_loop(self):
        print(f"[{datetime.now()}] Starting Basis Arb Real-time Engine...")
        print(f"Target Asset: {self.asset} | Entry Threshold: {self.threshold*100}%")

        while True:
            try:
                if not self.active_position:
                    self.check_for_opportunities()
                else:
                    self.monitor_position()
                
                # Update Shared State for API
                shared_bot_state["active_position"] = self.active_position
                shared_bot_state["status"] = "running"
                shared_bot_state["last_update"] = str(datetime.now())

                time.sleep(60) # Checar a cada minuto
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(10)

    def check_for_opportunities(self):
        # 1. Buscar contratos
        contracts = self.engine.fetch_delivery_contracts(asset=self.asset)
        
        results = []
        for c in contracts:
            symbol = c['symbol']
            # Para o Basis, comparamos o Spot (USDT) com o Futuro de Entrega (USD)
            data = self.engine.fetch_basis_data(spot_symbol=f"{self.asset}USDT", delivery_symbol=symbol)
            if data:
                expiry = self.logic.parse_expiry(symbol)
                y = self.logic.calculate_annualized_yield(data['spot'], data['future'], expiry)
                results.append({**data, 'symbol': symbol, 'yield': y, 'expiry_date': str(expiry)})
        
        best = self.logic.get_best_contract(results)
        
        if best and best['annualized_yield'] > self.threshold:
            print(f">>> OPPORTUNITY DETECTED: {best['symbol']} | Yield: {best['annualized_yield']*100:.2f}%")
            self.execute_entry(best)
        else:
            current_best = f"{best['symbol']} ({best['annualized_yield']*100:.2f}%)" if best else "None"
            print(f"[{datetime.now()}] Monitoring... Best: {current_best}")

    def execute_entry(self, contract):
        print(f"!!! EXECUTING ENTRY on {contract['symbol']} !!!")
        # Em produção, aqui chamariam as APIs de Ordem (create_order)
        # 1. Comprar Spot
        # 2. Transferir para Margem COIN-M
        # 3. Abrir Short 1x
        
        self.active_position = {
            'symbol': contract['symbol'],
            'entry_spot': contract['spot'],
            'entry_future': contract['future'],
            'yield_locked': contract['yield'],
            'entry_time': str(datetime.now())
        }
        self.save_state(self.active_position)
        print("Position stored in state.json")

    def monitor_position(self):
        # Basis Arb é segurar até o vencimento ou até uma compressão prematura do spread
        pos = self.active_position
        
        # Real-time check of current basis for the active position
        data = self.engine.fetch_basis_data(spot_symbol=f"{self.asset}USDT", delivery_symbol=pos['symbol'])
        current_yield = 0
        if data:
            expiry = self.logic.parse_expiry(pos['symbol'])
            current_yield = self.logic.calculate_annualized_yield(data['spot'], data['future'], expiry)
            
        print(f"[{datetime.now()}] Holding {pos['symbol']} | Locked: {pos['yield_locked']*100:.2f}% | Current: {current_yield*100:.2f}%")
        
        # Update Shared State for API
        shared_bot_state["active_position"]["current_spot"] = data['spot'] if data else pos['entry_spot']
        shared_bot_state["active_position"]["current_future"] = data['future'] if data else pos['entry_future']
        shared_bot_state["active_position"]["current_yield_apr"] = current_yield
        
        # Check for early exit or close to expiry logic here
        pass

def start_api():
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    # Start API in a separate thread
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    bot = BasisArbRealtime()
    bot.run_loop()
