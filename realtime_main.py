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
from collections import deque

# FastAPI Instance
app = FastAPI()

# Shared state for API
shared_bot_state = {
    "status": "initializing",
    "strategy": "Basis Arbitrage COIN-M",
    "active_position": None,
    "last_update": None,
    "logs": []
}

MAX_LOGS = 50
bot_logs = deque(maxlen=MAX_LOGS)

def log_event(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)
    bot_logs.append(formatted_msg)
    shared_bot_state["logs"] = list(bot_logs)

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
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                return None
        return None

    def save_state(self, state):
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

    def run_loop(self):
        log_event(f"Starting Basis Arb Real-time Engine...")
        log_event(f"Target Asset: {self.asset} | Entry Threshold: {self.threshold*100}%")

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
                log_event(f"Error in main loop: {e}")
                time.sleep(10)

    def check_for_opportunities(self):
        # 1. Buscar contratos
        contracts = self.engine.fetch_delivery_contracts(asset=self.asset)
        
        results = []
        for c in contracts:
            symbol = c['symbol']
            data = self.engine.fetch_basis_data(spot_symbol=f"{self.asset}USDT", delivery_symbol=symbol)
            if data:
                expiry = self.logic.parse_expiry(symbol)
                y = self.logic.calculate_annualized_yield(data['spot'], data['future'], expiry)
                results.append({**data, 'symbol': symbol, 'yield': y, 'expiry_date': str(expiry)})
        
        best = self.logic.get_best_contract(results)
        
        if best and best['annualized_yield'] > self.threshold:
            log_event(f">>> OPPORTUNITY DETECTED: {best['symbol']} | Yield: {best['annualized_yield']*100:.2f}%")
            self.execute_entry(best)
        else:
            current_best = f"{best['symbol']} ({best['annualized_yield']*100:.2f}%)" if best else "None"
            log_event(f"Monitoring... Best: {current_best}")

    def execute_entry(self, contract):
        log_event(f"!!! EXECUTING ENTRY on {contract['symbol']} !!!")
        
        self.active_position = {
            'symbol': contract['symbol'],
            'entry_spot': contract['spot'],
            'entry_future': contract['future'],
            'yield_locked': contract['yield'],
            'entry_time': str(datetime.now())
        }
        self.save_state(self.active_position)
        log_event("Position stored in state.json")

    def monitor_position(self):
        pos = self.active_position
        
        # Always parse expiry from symbol even if API fails (e.g. delisted)
        expiry_date = self.logic.parse_expiry(pos['symbol'])
        
        data = self.engine.fetch_basis_data(spot_symbol=f"{self.asset}USDT", delivery_symbol=pos['symbol'])
        current_yield = 0
        
        if data:
            current_yield = self.logic.calculate_annualized_yield(data['spot'], data['future'], expiry_date)
            
        log_event(f"Holding {pos['symbol']} | Locked: {pos['yield_locked']*100:.2f}% | Current: {current_yield*100:.2f}%")
        
        # Update Shared State for API (Ensure we update the global dict)
        shared_bot_state["active_position"] = pos
        if data:
            shared_bot_state["active_position"]["current_spot"] = data['spot']
            shared_bot_state["active_position"]["current_future"] = data['future']
            shared_bot_state["active_position"]["current_yield_apr"] = current_yield

        # =========================================================
        # AUTOMATION: Expiry Detection (The Reinvestment Trigger)
        # =========================================================
        now = datetime.now()
        # Ensure we are comparing same types (naive vs naive)
        if expiry_date:
            expiry_naive = expiry_date.replace(tzinfo=None)
            now_naive = now.replace(tzinfo=None)
            
            if now_naive >= expiry_naive:
                log_event(f">>> 🚨 CONTRACT EXPIRED ({pos['symbol']})! Mathematical convergence reached.")
                self.execute_exit(reason="Contract Expiry - Ready to Reinvest")

    def execute_exit(self, reason):
        log_event(f"!!! CLOSING POSITION !!! Reason: {reason}")
        
        # Clear local and shared state
        self.active_position = None
        shared_bot_state["active_position"] = None
        
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
            
        log_event("✅ Position cleared. Bot returning to scanning mode for next opportunity...")

def start_api():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

if __name__ == "__main__":
    # Start API in a separate thread
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    bot = BasisArbRealtime()
    bot.run_loop()
