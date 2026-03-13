from data_engine import DataEngine
from basis_logic import BasisLogic
from risk_manager import RiskManager
import os
import time
from datetime import datetime
import json

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
        print(f"[{datetime.now()}] Holding {pos['symbol']} | Locked: {pos['yield_locked']*100:.2f}%")
        # Check for early exit or close to expiry logic here
        pass

if __name__ == "__main__":
    bot = BasisArbRealtime()
    bot.run_loop()
