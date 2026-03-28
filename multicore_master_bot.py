import time
import os
import sys
import json
import requests
import queue
import threading
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Thread

# Import custom modules
from data.data_engine import DataEngine
from logic.mirofish_client import MiroFishClient
from logic.basis_logic import BasisLogic
from logic.ml_brain import MLBrain
from logic.order_flow_logic import OrderFlowLogic

# Forçar unbuffered stdout
sys.stdout.reconfigure(line_buffering=True)

class NumpyEncoder(json.JSONEncoder):
    """ Custom encoder for numpy data types """
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

class MulticoreMasterBot:
    def __init__(self, assets=["BTCBRL", "ETHBRL", "SOLBRL"], cofre_threshold=0.08):
        self.assets = assets
        self.cofre_threshold = cofre_threshold
        self.history_log = [] 
        self.log_file = "results/signals_log.txt"
        self.status_file = "results/bot_status.json"
        
        # Risk Management
        self.stop_loss = 0.015  # 1.5%
        self.take_profit = 0.03 # 3.0%
        
        # Paper Trading Basics
        self.fee_rate = 0.001 
        self.trade_threshold = 0.65 
        self.min_binance_amount = 10.0 # Minimo Binance (R$)
        self.trade_amount = 100.0     # Valor fixado por trade (R$)
        self.balance_file = "results/balance_state.txt"
        self.paper_log = "results/paper_trades_log.txt"

        # MiroFish Settings
        self.last_sentiment = {"sentiment": "Neutral", "confidence": 0.5, "updated": ""}
        self.mf_client = MiroFishClient()
        self.mf_project_id = "trading_sentiment_auto"
        self.mf_simulation_id = None # To be updated dynamically
        
        # Load Existing State
        self.balance = self.load_balance()
        self.positions = self.load_state() # This will populate self.mf_simulation_id if it exists
        
        # Modules
        self.engine = DataEngine()
        self.basis_logic = BasisLogic()
        self.of_logic = OrderFlowLogic()
        
        # ML Brains
        self.brains = {asset: MLBrain() for asset in assets}
        self.stats = {asset: {"history_days": 0, "samples": 0, "oos_score": 0.0} for asset in assets}
        
        # Async I/O Logging Queue
        self.log_queue = queue.Queue()
        self.log_thread = Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()
        
        # Lock for thread-safe position updates
        self.pos_lock = Lock()

        # Thread Pool Executor (Persistent)
        self.executor = ThreadPoolExecutor(max_workers=len(self.assets))
        
        print(f"[INIT] Inicializando Motores e Treinando Cerebro...")
        for asset in assets:
            limit = 1500
            df = self.engine.fetch_binance_klines(asset, limit=limit)
            if not df.empty:
                df = self.engine.apply_indicators(df)
                # Capta o score OOS real do treino em vez de valor aleatorio
                oos_score = self.brains[asset].train(df, train_full=False, tp=self.take_profit, sl=self.stop_loss)
                self.stats[asset]["history_days"] = len(df) / 24
                self.stats[asset]["samples"] = len(df)
                self.stats[asset]["oos_score"] = oos_score
        
        print(f"Master Bot Multicore Pronto!")

    def load_balance(self):
        if os.path.exists(self.balance_file):
            try:
                with open(self.balance_file, "r") as f:
                    return float(f.read().strip())
            except: pass
        return 1000.0

    def _log_worker(self):
        """ Daemon thread for Async I/O operations """
        while True:
            task = self.log_queue.get()
            if task is None: break
            action, data = task
            try:
                if action == "append":
                    filepath, content = data
                    with open(filepath, "a", encoding="utf-8") as f:
                        f.write(content + "\n")
                elif action == "write":
                    filepath, content = data
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                elif action == "save_state":
                    filepath, state_data = data
                    with open(filepath, "w") as f:
                        json.dump(state_data, f, cls=NumpyEncoder, indent=4)
            except Exception as e:
                print(f"[IO ERROR] {e}")
            self.log_queue.task_done()

    def async_log(self, filepath, content):
        self.log_queue.put(("append", (filepath, content)))

    def save_balance(self):
        self.log_queue.put(("write", (self.balance_file, f"{self.balance:.2f}")))

    def load_state(self):
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r") as f:
                    data = json.load(f)
                    self.balance = data.get("balance", self.balance)
                    self.trade_amount = data.get("trade_amount", 100.0)
                    self.last_sentiment = data.get("sentiment", self.last_sentiment)
                    self.mf_simulation_id = data.get("mf_simulation_id", self.mf_simulation_id)
                    print(f"✅ Estado anterior carregado: {len(data.get('positions', {}))} posicoes.")
                    return data.get('positions', {})
            except Exception as e:
                print(f"Erro ao carregar estado: {e}")
        return {}

    def save_state(self):
        try:
            state = {
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "balance": self.balance,
                "trade_amount": self.trade_amount,
                "sentiment": self.last_sentiment,
                "mf_simulation_id": self.mf_simulation_id,
                "positions": self.positions.copy()
            }
            self.log_queue.put(("save_state", (self.status_file, state)))
        except Exception as e:
            print(f"Erro ao enfileirar estado: {e}")

    def update_mirofish_sentiment(self):
        """Periodically update sentiment from MiroFish."""
        try:
            # Look for existing simulation report first
            if not self.mf_simulation_id:
                print(f"[MIROFISH] Iniciando nova simulacao de sentimento...")
                create_res = self.mf_client.create_simulation(self.mf_project_id)
                if create_res.get("success"):
                    self.mf_simulation_id = create_res.get("data", {}).get("simulation_id")
                    print(f"[MIROFISH] Simulacao criada: {self.mf_simulation_id}")
                    # Prepare and start
                    self.mf_client.prepare_simulation(self.mf_simulation_id)
                    self.mf_client.start_simulation(self.mf_simulation_id)
                    print(f"[MIROFISH] Analise iniciada. Aguardando relatorio...")
                else:
                    print(f"[MIROFISH] Falha ao criar simulacao: {create_res.get('error')}")
            
            if self.mf_simulation_id:
                res = self.mf_client.get_sentiment_summary(self.mf_simulation_id)
                # If report not ready yet, trigger generation just in case
                if res.get("sentiment") == "Neutral" and res.get("confidence") == 0:
                     self.mf_client.generate_report(self.mf_simulation_id)
                
                self.last_sentiment = {
                    "sentiment": res.get("sentiment", "Neutral"),
                    "confidence": res.get("confidence", 0.5),
                    "updated": datetime.now().strftime('%H:%M:%S')
                }
                print(f"MiroFish Sentiment Updated: {self.last_sentiment['sentiment']} ({self.last_sentiment['confidence']:.2f})")
        except Exception as e:
            # logger.error(f"Error updating MiroFish sentiment: {e}")
            print(f"Error updating MiroFish sentiment: {e}")

    def run(self):
        print(f"Iniciando Loop de Execucao (Intervalo: 30s)")
        iter_count = 0
        while True:
            try:
                timestamp = datetime.now().strftime('%H:%M:%S')
                # os.system('cls' if os.name == 'nt' else 'clear')
                
                # Salva estado no inicio do loop
                self.save_state()
                
                # Calculate Total Equity (Balance + current value of all open positions)
                total_equity = self.balance
                for p_asset in self.positions:
                    p_pos = self.positions[p_asset]
                    # Market value = trade_amount + (trade_amount * pnl_pct)
                    p_entry_val = self.trade_amount 
                    p_pnl_pct = ((p_pos.get('current_price', p_pos['entry']) / p_pos['entry']) - 1) * p_pos['signal']
                    p_market_val = p_entry_val * (1 + p_pnl_pct)
                    total_equity += p_market_val

                print(f"+{'-'*72}+")
                print(f"| >>> ADVANCED MULTICORE BTC BOT | {timestamp} | Equity: R$ {total_equity:9.2f} |")
                print(f"| Saldo Disponivel: R$ {self.balance:8.2f}  | Posicoes Abertas: {len(self.positions):2}         |")
                print(f"+{'-'*72}+")
                
                # TIER 1: PORTFOLIO
                if self.positions:
                    print(f"| [PORTFOLIO] Ativos em Carteira:                                        |")
                    for p_asset, p_pos in self.positions.items():
                        p_side = "COMPRA" if p_pos['signal'] == 1 else "VENDA "
                        p_pnl_pct = ((p_pos.get('current_price', p_pos['entry']) / p_pos['entry']) - 1) * p_pos['signal']
                        p_val_brl = self.trade_amount * (1 + p_pnl_pct)
                        print(f"|    {p_asset:9}: {p_pos['qty']:10.6f} {p_side} | Valor: R$ {p_val_brl:8.2f} | PnL: {p_pnl_pct:+.2%} |")
                    print(f"+{'-'*72}+")
                
                # TIER 1: COFRE
                contracts = self.engine.fetch_delivery_contracts(asset="BTC")
                basis_results = []
                for c in contracts:
                    data = self.engine.fetch_basis_data(spot_symbol="BTCBRL", delivery_symbol=c['symbol'])
                    if data:
                        expiry = self.basis_logic.parse_expiry(c['symbol'])
                        y = self.basis_logic.calculate_annualized_yield(data['spot'], data['future'], expiry)
                        basis_results.append({**data, 'symbol': c['symbol'], 'yield_apr': y, 'expiry_date': str(expiry)})
                
                best_basis = self.basis_logic.get_earliest_profitable_contract(basis_results, self.cofre_threshold)
                highest = self.basis_logic.get_best_contract(basis_results)
                curr_y = (highest['yield_apr'] * 100) if highest else 0
                
                status_cofre = "OPORTUNIDADE!" if best_basis else "MONITORANDO"
                print(f"| [COFRE BRL] Status: {status_cofre:17} | Melhor Yield BTC: {curr_y:6.2f}% a.a. |")
                print(f"+{'-'*72}+")
                
                # TIER 2: ALPHA
                print(f"| [ALPHA ML ] Sinais em tempo real (BRL) baseados em Order Flow:       |")
                
                def process_asset(asset):
                    try:
                        df_ml = self.engine.fetch_binance_klines(asset, limit=100)
                        if df_ml.empty: return
                        df_ml = self.engine.apply_indicators(df_ml)
                        processed_ml = self.brains[asset].prepare_features(df_ml)
                        feature_cols = [c for c in processed_ml.columns if c.startswith('feat_')]
                        last_features = processed_ml[feature_cols].iloc[-1].values
                        signal, prob, reason = self.brains[asset].predict_signal(last_features, feature_cols)
                        
                        current_price = df_ml['close'].iloc[-1]
                        
                        with self.pos_lock:
                            # 1. Check Positions
                            if asset in self.positions:
                                self.positions[asset]['current_price'] = current_price # Update live price
                                pos = self.positions[asset]
                                price_ret = (current_price / pos['entry']) - 1
                                trade_pnl = price_ret * pos['signal']
                                
                                exit_reason = None
                                if trade_pnl >= self.take_profit: exit_reason = "TAKE PROFIT"
                                elif trade_pnl <= -self.stop_loss: exit_reason = "STOP LOSS"
                                
                                if exit_reason:
                                    total_trade_fee = self.fee_rate * 2
                                    net_pnl_pct = trade_pnl - total_trade_fee
                                    profit_brl = self.trade_amount * net_pnl_pct
                                    self.balance += (self.trade_amount + profit_brl) # Retorna capital + lucro
                                    self.save_balance()
                                    log_exit = f"[{timestamp}] FECHADO {asset}: {exit_reason} | PnL Liquid: {net_pnl_pct:+.2%} | Saldo: R$ {self.balance:.2f}"
                                    self.history_log.insert(0, log_exit)
                                    self.async_log(self.paper_log, log_exit)
                                    self.async_log(self.log_file, log_exit)
                                    del self.positions[asset]
                                    self.save_state() # Update state immediately after exit
                            
                            # 2. Open Positions
                            elif signal != 0 and prob >= self.trade_threshold:
                                # Apply Sentiment Bias
                                bias = 0.0
                                if self.last_sentiment["sentiment"] == "Bullish" and signal == 1:
                                    bias = 0.05
                                elif self.last_sentiment["sentiment"] == "Bearish" and signal == -1:
                                    bias = 0.05
                                
                                effective_prob = prob + bias
                                
                                if effective_prob >= self.trade_threshold:
                                    if self.balance >= self.trade_amount and self.trade_amount >= self.min_binance_amount:
                                        qty = self.trade_amount / current_price
                                        side = "COMPRA" if signal == 1 else "VENDA"
                                        self.positions[asset] = {
                                            "entry": current_price,
                                            "signal": signal,
                                            "qty": qty,
                                            "prob": prob,
                                            "effective_prob": effective_prob,
                                            "time": datetime.now().strftime('%H:%M:%S'),
                                            "current_price": current_price
                                        }
                                        self.balance -= self.trade_amount # Deduct trade amount for paper trading
                                        log_entry = f"[{timestamp}] ABERTO {asset}: {side} @ {current_price:.2f} (Qtd: {qty:.6f}) | Saldo: R$ {self.balance:.2f}"
                                        self.history_log.insert(0, log_entry)
                                        self.async_log(self.paper_log, log_entry)
                                        self.async_log(self.log_file, log_entry)
                                        self.save_balance()
                                        self.save_state() # Update state immediately after entry

                            # Status Row
                            sig_text = "NADA"
                            sig_icon = " "
                            if asset in self.positions:
                                pos = self.positions[asset]
                                pnl_pct = ((current_price / pos['entry']) - 1) * pos['signal']
                                sig_text = f"ABERTO ({pnl_pct:+.2%})"
                                sig_icon = "B" if pos['signal'] == 1 else "S"
                            elif signal == 1: sig_text = f"COMPRA ({prob:.0%})"; sig_icon = "+"
                            elif signal == -1: sig_text = f"VENDA  ({prob:.0%})"; sig_icon = "-"
                            else: sig_text = f"NEUTRO ({prob:.0%})"; sig_icon = "."
                            
                            oos_acc = self.stats[asset]["oos_score"]
                            print(f"|    {sig_icon} {asset:9}: {sig_text:18} - {reason:18} |")
                            print(f"|      (Confianca: {oos_acc:2.0%} | SL: 1.5% | TP: 3.0%)                   |")
                            
                            log_ml = f"[{timestamp}] {asset:9}: {sig_text:18} - {reason:18} | Confianca: {oos_acc:2.0%} | SL: 1.5% | TP: 3.0%"
                            self.async_log(self.log_file, log_ml)

                    except Exception as e:
                        print(f"Erro processando {asset}: {e}")

                # Execute asset processing concurrently using persistent executor
                list(self.executor.map(process_asset, self.assets))
                
                self.history_log = self.history_log[:5]
                print(f"+{'-'*72}+")
                print(f"| # LOG RECENTE:                                                        |")
                for entry in self.history_log:
                    clean_entry = entry.encode('ascii', 'ignore').decode('ascii')
                    print(f"| > {clean_entry:68} |")
                print(f"+{'-'*72}+")
                
            except Exception as e:
                print(f"Error in loop: {e}")
            
            iter_count += 1
            # Update MiroFish sentiment every ~100 iterations (approx every 15-20 mins)
            if iter_count % 100 == 0:
                self.update_mirofish_sentiment()
                
            time.sleep(30)

if __name__ == "__main__":
    bot = MulticoreMasterBot()
    bot.run()
