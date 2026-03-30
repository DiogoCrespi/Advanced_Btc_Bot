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

import math
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance.enums import *

load_dotenv()

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
    def __init__(self, assets=["BTCBRL", "ETHBRL", "SOLBRL"], cofre_threshold=0.08, live_mode=False):
        self.live_mode = live_mode
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.client = None
        
        self.assets = assets
        self.cofre_threshold = cofre_threshold
        self.history_log = [] 
        self.log_file = "results/signals_log.txt"
        self.status_file = "results/bot_status.json"
        self.start_time = datetime.now()  # Uptime tracking
        
        # Validar modo de execução
        if self.live_mode:
            print("[SISTEMA] 🚨 MODO LIVE TRADING ATIVADO! Validando chaves API...")
            self._validate_api_keys()
        else:
            print("[SISTEMA] 🎮 Modo SIMULAÇÃO (Paper Trading) Misto.")
        
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

    def _validate_api_keys(self):
        if not self.api_key or not self.api_secret:
            print("[ERRO FATAL] Chaves BINANCE_API_KEY e BINANCE_API_SECRET ausentes no .env!")
            sys.exit(1)
        try:
            self.client = Client(self.api_key, self.api_secret)
            account_info = self.client.get_account()
            if not account_info.get('canTrade'):
                print("[ERRO FATAL] As chaves API não têm permissão de Trading habilitada!")
                sys.exit(1)
            print("✅ Conectado na Binance! Permissão de leitura/trading ativa.")
        except BinanceAPIException as e:
            print(f"[ERRO FATAL] Credenciais rejeitadas pela Binance: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERRO FATAL] Falha de rede ao conectar com a Binance: {e}")
            sys.exit(1)
            
    def get_real_balance(self, asset='BRL'):
        """Retorna o saldo real (Free Balance) da carteira Spot."""
        if not self.live_mode or not self.client: return self.balance
        try:
            asset_info = self.client.get_asset_balance(asset=asset)
            return float(asset_info['free']) if asset_info else 0.0
        except:
            return self.balance # fallback
            
    def format_quantity(self, asset, raw_qty):
        """Formata a fração da ordem perfeitamente no stepSize obrigatório da Binance para evitar falha no envio."""
        try:
            info = self.client.get_symbol_info(asset)
            step_size = None
            for f in info['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    break
            if step_size:
                precision = int(round(-math.log(step_size, 10), 0))
                return math.floor(raw_qty * (10**precision)) / (10**precision)
        except: pass
        return round(raw_qty, 5)

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

    def _get_uptime_str(self):
        """Retorna a string de uptime formatada: Xd Xh Xm Xs"""
        delta = datetime.now() - self.start_time
        total_seconds = int(delta.total_seconds())
        days    = total_seconds // 86400
        hours   = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"

    def run(self):
        print(f"Iniciando Loop de Execucao (Intervalo: 30s)")
        print(f"[UPTIME] Bot iniciado em: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        iter_count = 0
        while True:
            try:
                timestamp = datetime.now().strftime('%H:%M:%S')
                uptime_str = self._get_uptime_str()
                # os.system('cls' if os.name == 'nt' else 'clear')
                
                # Salva estado no inicio do loop
                self.save_state()
                
                # Fetch Real Balance if Live
                if self.live_mode:
                    self.balance = self.get_real_balance('BRL')
                
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
                print(f"| Uptime: {uptime_str:<63}|")
                print(f"+{'-'*72}+")
                # Log de uptime no arquivo a cada iteracao
                self.async_log(self.log_file, f"[{timestamp}] [UPTIME] {uptime_str} | Iniciado: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
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
                        df_ml = self.engine.fetch_binance_klines(asset, limit=300)
                        if df_ml.empty: return
                        df_ml = self.engine.apply_indicators(df_ml)
                        processed_ml = self.brains[asset].prepare_features(df_ml)
                        feature_cols = [c for c in processed_ml.columns if c.startswith('feat_')]
                        last_features = processed_ml[feature_cols].values[-1]
                        signal, prob, reason = self.brains[asset].predict_signal(last_features, feature_cols)
                        
                        current_price = df_ml['close'].values[-1]
                        
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
                                    actual_pnl_pct = trade_pnl
                                    
                                    if self.live_mode and self.client:
                                        print(f"[LIVE] 🚨 Executando SAÍDA ({exit_reason}) para {asset}...")
                                        try:
                                            # Formata a quantidade para evitar erro de precisão
                                            exec_qty = self.format_quantity(asset, pos['qty'])
                                            order = self.client.create_order(
                                                symbol=asset,
                                                side=SIDE_SELL,
                                                type=ORDER_TYPE_MARKET,
                                                quantity=exec_qty
                                            )
                                            # Calcula PnL real baseado no preço de execução se disponível
                                            if order.get('fills'):
                                                avg_price = sum(float(f['price']) * float(f['qty']) for f in order['fills']) / sum(float(f['qty']) for f in order['fills'])
                                                actual_pnl_pct = ((avg_price / pos['entry']) - 1) * pos['signal']
                                                log_live = f"[LIVE] {asset} Vendido @ {avg_price:.2f}"
                                                print(log_live)
                                        except Exception as e:
                                            print(f"[LIVE ERROR] Falha ao fechar posição: {e}")
                                            # Em caso de erro crítico no live, não removemos a posição para tentar novamente ou manual
                                            return

                                    total_trade_fee = self.fee_rate * 2
                                    net_pnl_pct = actual_pnl_pct - total_trade_fee
                                    profit_brl = self.trade_amount * net_pnl_pct
                                    
                                    # No Live Mode o balance é atualizado via API no topo do loop, 
                                    # mas atualizamos aqui para o display imediato ser coerente
                                    self.balance += (self.trade_amount + profit_brl)
                                    self.save_balance()
                                    
                                    log_exit = f"[{timestamp}] FECHADO {asset}: {exit_reason} | PnL Liquid: {net_pnl_pct:+.2%} | Saldo: R$ {self.balance:.2f}"
                                    self.history_log.insert(0, log_exit)
                                    self.async_log(self.paper_log, log_exit)
                                    self.async_log(self.log_file, log_exit)
                                    del self.positions[asset]
                                    self.save_state() # Update state immediately after exit
                            
                            # 2. Open Positions
                            elif signal != 0:
                                # Bloqueio de Segurança: Evita Short em Mercado Spot (BRL/USDT)
                                if signal == -1 and ('BRL' in asset or 'USDT' in asset):
                                    reason = "Short Blocked (Spot)"
                                    signal = 0

                                if signal != 0:
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
                                            entry_price = current_price
                                            
                                            if self.live_mode and self.client:
                                                print(f"[LIVE] 🚀 Abrindo COMPRA para {asset}...")
                                                try:
                                                    # No mercado Spot, calculamos a qty baseada no valor BRL fixo
                                                    # Algumas moedas exigem precisão específica
                                                    exec_qty = self.format_quantity(asset, qty)
                                                    order = self.client.create_order(
                                                        symbol=asset,
                                                        side=SIDE_BUY,
                                                        type=ORDER_TYPE_MARKET,
                                                        quantity=exec_qty
                                                    )
                                                    if order.get('fills'):
                                                        entry_price = sum(float(f['price']) * float(f['qty']) for f in order['fills']) / sum(float(f['qty']) for f in order['fills'])
                                                        qty = sum(float(f['qty']) for f in order['fills']) # Qtd real executada
                                                except Exception as e:
                                                    print(f"[LIVE ERROR] Falha ao abrir posição: {e}")
                                                    return

                                            side = "COMPRA" if signal == 1 else "VENDA"
                                            self.positions[asset] = {
                                                "entry": entry_price,
                                                "signal": signal,
                                                "qty": qty,
                                                "prob": prob,
                                                "effective_prob": effective_prob,
                                                "time": datetime.now().strftime('%H:%M:%S'),
                                                "current_price": entry_price
                                            }
                                            
                                            # No Live Mode, o saldo diminuirá na Binance automaticamente
                                            self.balance -= self.trade_amount 
                                            log_entry = f"[{timestamp}] ABERTO {asset}: {side} @ {entry_price:.2f} (Qtd: {qty:.6f}) | Saldo: R$ {self.balance:.2f}"
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
                
            # Retrain ML Models every ~2880 iterations (24 hours at 30s per iter)
            if iter_count % 2880 == 0:
                print(f"\n[SISTEMA] Iniciando Retreinamento Diário dos Modelos de ML...")
                for rt_asset in self.assets:
                    try:
                        df_rt = self.engine.fetch_binance_klines(rt_asset, limit=1500)
                        if not df_rt.empty:
                            df_rt = self.engine.apply_indicators(df_rt)
                            oos_sc = self.brains[rt_asset].train(df_rt, train_full=False, tp=self.take_profit, sl=self.stop_loss)
                            self.stats[rt_asset]["samples"] = len(df_rt)
                            self.stats[rt_asset]["oos_score"] = oos_sc
                            print(f"[RE-TRAINED] {rt_asset} OOS Score: {oos_sc:.2%}")
                    except Exception as e:
                        print(f"Erro ao retreinar {rt_asset}: {e}")
                print("\n")
                
            time.sleep(30)

if __name__ == "__main__":
    bot = MulticoreMasterBot()
    bot.run()
