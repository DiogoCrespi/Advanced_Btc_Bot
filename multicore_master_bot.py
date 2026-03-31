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
# removed: fastapi, uvicorn imports

import math
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance.enums import *

load_dotenv()

# Import custom modules
from data.data_engine import DataEngine
from logic.basis_logic import BasisLogic
from logic.ml_brain import MLBrain
from logic.order_flow_logic import OrderFlowLogic
from logic.xaut_logic import XAUTAnalyzer
from logic.market_memory import MarketMemory
from logic.strategist_agent import StrategistAgent

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
        self.equity_history = [] # For dashboard charts
        
        # Validar modo de execução
        if self.live_mode:
            print("[SISTEMA] 🚨 MODO LIVE TRADING ATIVADO! Validando chaves API...")
            self._validate_api_keys()
        else:
            print("[SISTEMA] 🎮 Modo SIMULAÇÃO (Paper Trading) Misto.")
        
        self.trade_amount = 100.0   # Base fallback
        self.risk_per_trade_pct = 0.05 # 5% per trade
        self.fee_rate = 0.001       # 0.1% Binance Standard
        self.take_profit = 0.03     # 3% Base
        self.stop_loss = 0.015      # 1.5% Base
        self.trailing_activation = 0.015 # Activate trailing at 1.5% profit
        self.trailing_callback = 0.005 # 0.5% pullback from peak
        
        # Paper Trading Basics
        self.trade_threshold = 0.55 
        self.min_binance_amount = 10.0 # Minimo Binance (R$)
        self.balance_file = "results/balance_state.txt"
        self.paper_log = "results/paper_trades_log.txt"

        # ── TIER 3: Estratégia XAUT/BTC ──────────────────────────────────────
        # Agora o capital vem das posições abertas de BTCBRL
        self.xaut_max_positions   = int(os.getenv("XAUT_MAX_POSITIONS",      "3"))
        self.xaut_sl_pct          = float(os.getenv("XAUT_STOP_LOSS_PCT",    "0.02"))
        self.xaut_tp_pct          = float(os.getenv("XAUT_TAKE_PROFIT_PCT",  "0.04"))
        self.xaut_signal_threshold= 0.55 
        self.xaut_positions       = []     # Lista de posições abertas em XAUT
        self.xaut_pos_counter     = 0
        self.xaut_log             = "results/xaut_trades.txt"
        self.xaut_analyzer        = XAUTAnalyzer()
        self.xaut_lock            = Lock()
        self.xaut_history         = [] 

        # Macro Context
        self.last_sentiment = {"sentiment": "Neutral", "confidence": 0.5, "updated": ""}
        
        # Load Existing State
        self.balance = self.load_balance()
        self.positions = self.load_state() # This will populate self.mf_simulation_id if it exists
        
        # Modules
        self.engine = DataEngine()
        self.basis_logic = BasisLogic()
        self.of_logic = OrderFlowLogic()
        
        # ML Brains
        self.brains = {asset: MLBrain() for asset in assets}
        self.agent = StrategistAgent() # New Agentic Layer
        self.memory = MarketMemory() # Knowledge retrieval layer
        self.stats = {asset: {"history_days": 0, "samples": 0, "oos_score": 0.0} for asset in assets}
        
        # Async I/O Logging Queue
        self.log_queue = queue.Queue()
        self.log_thread = Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()
        
        # Lock for thread-safe position updates
        self.pos_lock = Lock()

        # Thread Pool Executor (Persistent)
        self.executor = ThreadPoolExecutor(max_workers=len(self.assets))
        
        # Dashboard/API Removed
        self.total_equity = self.balance # Initial state
        
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

    # _setup_routes and _run_api removed

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
                    self.trade_amount = data.get("trade_amount", 500.0)
                    self.last_sentiment = data.get("sentiment", self.last_sentiment)
                    # Restaurar posições XAUT/BTC
                    self.xaut_positions = data.get("xaut_positions", [])
                    self.xaut_pos_counter = data.get("xaut_pos_counter", 0)
                    
                    n_xaut = len(self.xaut_positions)
                    n_brl = len(data.get('positions', {}))
                    print(f"✅ Estado anterior carregado: {n_brl} posicoes BRL | {n_xaut} posicoes XAUT.")
                    return data.get('positions', {})
            except Exception as e:
                print(f"Erro ao carregar estado: {e}")
        return {}

    def save_state(self):
        try:
            with self.pos_lock:
                state = {
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "balance": self.balance,
                    "trade_amount": self.trade_amount,
                    "sentiment": self.last_sentiment,
                    "positions": self.positions.copy(),
                    "xaut_positions":    list(self.xaut_positions),
                    "xaut_pos_counter":  self.xaut_pos_counter
                }
            self.log_queue.put(("save_state", (self.status_file, state)))
        except Exception as e:
            print(f"Erro ao enfileirar estado: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # TIER 3 — Estratégia XAUT/BTC
    # ─────────────────────────────────────────────────────────────────────────

    def _process_xaut(self, timestamp: str) -> list:
        display_lines = []

        # 1. Busca estoque de BTC disponível do ALPHA (BTCBRL)
        with self.pos_lock:
            # Pega a lista de BTC de todas as posições abertas de BTCBRL
            btc_pos_list = self.positions.get('BTCBRL', [])
            if not isinstance(btc_pos_list, list):
                # Retrocompatibilidade: se for dict unico, converte para lista
                btc_pos_list = [btc_pos_list] if btc_pos_list else []
                self.positions['BTCBRL'] = btc_pos_list
            
            total_btc_holdings = sum(p['qty'] for p in btc_pos_list)
            # Reservamos o BTC que já está em XAUT (não podemos gastar 2x)
            btc_in_xaut = sum(p['cost_btc'] for p in self.xaut_positions)
            available_btc = total_btc_holdings - btc_in_xaut

        # 2. Busca dados do ratio
        df_xaut = self.engine.fetch_xaut_ratio(limit=300)
        if df_xaut.empty:
            display_lines.append("| [XAUT/BTC] Sem dados disponíveis — aguardando...            |")
            return display_lines

        last_row      = df_xaut.iloc[-1]
        current_ratio = float(last_row['close'])
        rsi_ratio     = float(last_row.get('ratio_rsi', 50))
        bb_pct        = float(last_row.get('bb_pct', 0.5))

        signal, confidence, reason = self.xaut_analyzer.get_signal(df_xaut)

        closed_this_cycle = []

        with self.xaut_lock:
            # ── 2. Gerenciar posições abertas ────────────────────────────
            remaining = []
            for pos in self.xaut_positions:
                pos['current_ratio'] = current_ratio
                pnl_pct = self.xaut_analyzer.calc_pnl_pct(pos, current_ratio)
                pnl_btc = self.xaut_analyzer.calc_pnl_btc(pos, current_ratio)

                exit_reason = None
                if pnl_pct >= self.xaut_tp_pct:
                    exit_reason = "TAKE PROFIT"
        # 3. Gerenciamento de Posições (Saídas em BTC)
        closed_this_cycle = []
        with self.xaut_lock:
            remaining = []
            for pos in self.xaut_positions:
                pnl_pct = self.xaut_analyzer.calc_pnl_pct(pos, current_ratio)
                
                exit_reason = None
                if pnl_pct >= self.xaut_tp_pct: exit_reason = "TAKE PROFIT"
                elif pnl_pct <= -self.xaut_sl_pct: exit_reason = "STOP LOSS"

                if exit_reason:
                    # Calcula PnL líquido (taxa estimada 0.2%)
                    fee_btc = pos['cost_btc'] * 0.002
                    recovered_btc = (pos['xaut_qty'] * current_ratio) - fee_btc
                    net_pnl_btc = recovered_btc - pos['cost_btc']

                    log_exit = (
                        f"[{timestamp}] FECHADO XAUT #{pos['id']:03d}: {exit_reason} "
                        f"| PnL: {net_pnl_btc:+.6f} BTC ({pnl_pct:+.2%})"
                    )
                    self.xaut_history.insert(0, log_exit)
                    self.async_log(self.xaut_log, log_exit)
                    self.async_log(self.log_file, log_exit)
                    closed_this_cycle.append(log_exit)
                else:
                    remaining.append(pos)
            self.xaut_positions = remaining

        # 4. Abertura de Novas Posições (Vendas de BTC -> XAUT)
        # (Signal, confidence e reason já foram calculados acima na linha 285)
        
        # Tamanho fixo de aporte de BTC (aprox R$ 333 por slot se R$ 1000 total)
        # 0.0009 BTC é o valor real solicitado (3 posições de 0.0009 = 0.0027 BTC)
        trade_size_btc = 0.0009

        can_open = (
            signal == 1
            and confidence >= self.xaut_signal_threshold
            and len(self.xaut_positions) < self.xaut_max_positions
            and available_btc >= trade_size_btc
            and self.xaut_analyzer.is_dca_allowed(self.xaut_positions, current_ratio, min_distance_pct=0.015)
        )

        if can_open:
            with self.xaut_lock:
                self.xaut_pos_counter += 1
                qty_xaut = trade_size_btc / current_ratio
                new_pos = {
                    "id":           self.xaut_pos_counter,
                    "ratio_entry":  current_ratio,
                    "xaut_qty":     qty_xaut,
                    "cost_btc":     trade_size_btc,
                    "time":         timestamp,
                    "current_ratio": current_ratio,
                }
                self.xaut_positions.append(new_pos)

                log_entry = (
                    f"[{timestamp}] ABERTO  XAUT #{self.xaut_pos_counter:03d}: "
                    f"ratio={current_ratio:.6f} | {trade_size_btc:.6f} BTC -> {qty_xaut:.4f} XAUT "
                    f"({reason} {confidence:.0%})"
                )
                self.xaut_history.insert(0, log_entry)
                self.async_log(self.xaut_log, log_entry)
                self.async_log(self.log_file, log_entry)
                self.save_state()
                self.save_state()

        # Recortar histórico de display
        self.xaut_history = self.xaut_history[:5]

        # ── 4. Montar linhas de display ──────────────────────────────────
        n_open     = len(self.xaut_positions)
        total_cost = sum(p['cost_btc'] for p in self.xaut_positions)
        total_val  = sum(p['xaut_qty'] * current_ratio for p in self.xaut_positions)
        pool_pnl   = total_val - total_cost   # PnL latente total em BTC

        sig_icon = "+" if signal == 1 else ("-" if signal == -1 else ".")
        display_lines.append(
            f"| [XAUT/BTC] Ratio: {current_ratio:.6f} BTC/XAUT "
            f"| RSI ratio: {rsi_ratio:5.1f} | BB%: {bb_pct:.2f}        |"
        )
        display_lines.append(
            f"| Pool BTC: {available_btc:.5f} BTC livre   "
            f"| Posicoes: {n_open}/{self.xaut_max_positions} "
            f"| PnL latente: {pool_pnl:+.6f} BTC         |"
        )
        display_lines.append(
            f"|   {sig_icon} Sinal: {reason:<30} "
            f"| Conf: {confidence:.0%} | Thresh: {self.xaut_signal_threshold:.0%}   |"
        )

        for pos in self.xaut_positions:
            pnl_p = self.xaut_analyzer.calc_pnl_pct(pos, current_ratio)
            pnl_b = self.xaut_analyzer.calc_pnl_btc(pos, current_ratio)
            display_lines.append(
                f"|   #{pos['id']:03d} entry={pos['ratio_entry']:.6f} "
                f"qty={pos['xaut_qty']:.4f} XAUT "
                f"PnL={pnl_b:+.5f}BTC ({pnl_p:+.2%}) "
                f"       |"
            )

        if closed_this_cycle:
            display_lines.append(f"| [XAUT FECHADO] {closed_this_cycle[0][:68]:68} |")

        return display_lines


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
                
                # Salva estado no inicio do loop
                self.save_state()
                
                # Fetch Real Balance if Live
                if self.live_mode:
                    self.balance = self.get_real_balance('BRL')
                
                # 1. Calculo de Equity Total (Saldo + Valor de Mercado de todas as posições)
                total_equity = self.balance
                with self.pos_lock:
                    for p_asset, p_list in self.positions.items():
                        plist = p_list if isinstance(p_list, list) else [p_list]
                        for p_pos in plist:
                            p_pnl_pct = ((p_pos.get('current_price', p_pos['entry']) / p_pos['entry']) - 1) * p_pos['signal']
                            total_equity += self.trade_amount * (1 + p_pnl_pct)

                print(f"+{'-'*72}+")
                print(f"| >>> ADVANCED MULTICORE BTC BOT | {timestamp} | Equity: R$ {total_equity:9.2f} |")
                print(f"| Saldo Disponivel: R$ {self.balance:8.2f}  | Uptime: {uptime_str:<32} |")
                print(f"+{'-'*72}+")
                self.async_log(self.log_file, f"[{timestamp}] [UPTIME] {uptime_str} | Equity: R$ {total_equity:.2f}")
                self.total_equity = total_equity
                
                # Track equity history for dashboard (capped at 100 points)
                self.equity_history.append({
                    "time": timestamp,
                    "equity": round(total_equity, 2)
                })
                if len(self.equity_history) > 100: self.equity_history.pop(0)
                # TIER 1: PORTFOLIO
                if self.positions:
                    print(f"| [PORTFOLIO] Ativos em Carteira:                                        |")
                    with self.pos_lock:
                        for p_asset, p_list in self.positions.items():
                            plist = p_list if isinstance(p_list, list) else [p_list]
                            for i, p_pos in enumerate(plist):
                                p_side = "COMPRA" if p_pos['signal'] == 1 else "VENDA "
                                p_pnl_pct = ((p_pos.get('current_price', p_pos['entry']) / p_pos['entry']) - 1) * p_pos['signal']
                                p_val_brl = self.trade_amount * (1 + p_pnl_pct)
                                dca_tag = f"#{i+1}" if len(plist) > 1 else "  "
                                print(f"|    {p_asset:7} {dca_tag}: {p_pos['qty']:10.6f} {p_side} | Valor: R$ {p_val_brl:8.2f} | PnL: {p_pnl_pct:+.2%} |")
                    print(f"+{'-'*72}+")

                # TIER 1: COFRE (Basis Trading)
                contracts = self.engine.fetch_delivery_contracts(asset="BTC")
                basis_results = []
                for c in contracts:
                    data = self.engine.fetch_basis_data(spot_symbol="BTCBRL", delivery_symbol=c['symbol'])
                    if data:
                        expiry = self.basis_logic.parse_expiry(c['symbol'])
                        y = self.basis_logic.calculate_annualized_yield(data['spot'], data['future'], expiry)
                        basis_results.append({**data, 'symbol': c['symbol'], 'yield_apr': y, 'expiry_date': str(expiry)})

                highest = self.basis_logic.get_best_contract(basis_results)
                curr_y = (highest['yield_apr'] * 100) if highest else 0
                print(f"| [COFRE BRL] Melhor Yield BTC Futuros: {curr_y:6.2f}% a.a.                  |")
                print(f"+{'-'*72}+")

                # TIER 2: ALPHA ML
                print(f"| [ALPHA ML ] Sinais baseados em Order Flow & ML:                       |")
                
                def process_asset(asset):
                    try:
                        df_ml = self.engine.fetch_binance_klines(asset, limit=300)
                        if df_ml.empty: return
                        df_ml = self.engine.apply_indicators(df_ml)
                        processed_ml = self.brains[asset].prepare_features(df_ml)
                        last_features = processed_ml[[c for c in processed_ml.columns if c.startswith('feat_')]].values[-1]
                        signal, prob, reason = self.brains[asset].predict_signal(last_features, [c for c in processed_ml.columns if c.startswith('feat_')])
                        current_price = df_ml['close'].values[-1]

                        with self.pos_lock:
                            # 1. Check Existing Positions (DCA Loop)
                            active_pos = self.positions.get(asset, [])
                            if not isinstance(active_pos, list): active_pos = [active_pos] if active_pos else []
                            
                            remaining = []
                            for pos in active_pos:
                                pos['current_price'] = current_price
                                pnl = ((current_price / pos['entry']) - 1) * pos['signal']
                                exit_reason = None
                                
                                # Use dynamic TP/SL stored in position
                                current_tp = self.take_profit * pos.get('tp_mult', 1.0)
                                current_sl = self.stop_loss * pos.get('sl_mult', 1.0)
                                
                                # Trailing Stop Logic
                                if pnl > self.trailing_activation:
                                    if 'max_pnl' not in pos: pos['max_pnl'] = pnl
                                    else: pos['max_pnl'] = max(pos['max_pnl'], pnl)
                                    
                                    # If PnL drops by 'callback' amount from peak, exit
                                    if pnl < (pos['max_pnl'] - self.trailing_callback):
                                        exit_reason = f"TRAILING STOP ({pos['max_pnl']:.2%})"
                                
                                if not exit_reason:
                                    if pnl >= current_tp: exit_reason = "TAKE PROFIT"
                                    elif pnl <= -current_sl: exit_reason = "STOP LOSS"
                                    elif signal == -pos['signal'] and prob >= 0.75: exit_reason = "REVERSAL"

                                if exit_reason:
                                    if asset == "BTCBRL": # CHAINED EXIT
                                        with self.xaut_lock:
                                            if self.xaut_positions:
                                                print(f"[CASCATA] Fechando XAUT devido a saída do BTC...")
                                                for x_pos in self.xaut_positions:
                                                    if self.live_mode and self.client:
                                                        try:
                                                            x_qty = self.format_quantity("XAUTBTC", x_pos['xaut_qty'])
                                                            self.client.create_order(symbol="XAUTBTC", side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=x_qty)
                                                        except Exception as e: print(f"Erro cascata: {e}")
                                                self.xaut_positions = []
                                                self.async_log(self.log_file, f"[{timestamp}] CASCATA: XAUT fechado por saída de BTCBRL")

                                    if self.live_mode and self.client:
                                        try:
                                            exec_qty = self.format_quantity(asset, pos['qty'])
                                            self.client.create_order(symbol=asset, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=exec_qty)
                                        except Exception as e:
                                            print(f"Erro fechar {asset}: {e}")
                                            remaining.append(pos); continue

                                    net_pnl = pnl - (self.fee_rate * 2)
                                    # Use the specific trade cost for PnL calculation
                                    self.balance += pos['cost'] * (1 + net_pnl)
                                    log_out = f"[{timestamp}] FECHADO {asset}: {exit_reason} | PnL: {net_pnl:+.2%} | BRL: {self.balance:.2f}"
                                    self.history_log.insert(0, log_out)
                                    self.async_log(self.log_file, log_out)
                                    self.save_balance()
                                else:
                                    remaining.append(pos)
                            self.positions[asset] = remaining

                            # 2. Entries & DCA (Max 2 for BTC, 1 for others)
                            max_dca = 2 if asset == "BTCBRL" else 1
                            if signal == 1 and len(self.positions[asset]) < max_dca:
                                # AGENTIC GATE & ALPHA MODIFIERS
                                decision, agent_reason, modifiers = self.agent.assess_trade(asset, signal, prob, reason)
                                
                                if decision == "APPROVE":
                                    # DYNAMIC SIZING: Trade % of balance * size multiplier
                                    current_trade_size = (self.balance * self.risk_per_trade_pct) * modifiers['size_mult']
                                    
                                    if self.balance >= current_trade_size:
                                        qty = current_trade_size / current_price
                                        entry_p = current_price
                                        if self.live_mode and self.client:
                                            try:
                                                exec_qty = self.format_quantity(asset, qty)
                                                self.client.create_order(symbol=asset, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=exec_qty)
                                            except Exception as e: print(f"Erro abrir {asset}: {e}"); return

                                        self.positions[asset].append({
                                            "entry": entry_p, 
                                            "signal": 1, 
                                            "qty": qty, 
                                            "cost": current_trade_size,
                                            "time": timestamp, 
                                            "current_price": entry_p,
                                            "tp_mult": modifiers['tp_mult'],
                                            "sl_mult": modifiers['sl_mult']
                                        })
                                        self.balance -= current_trade_size
                                        log_in = f"[{timestamp}] ABERTO {asset} ({modifiers['size_mult']}x): @ {entry_p:.2f} | BRL: {self.balance:.2f}"
                                        self.history_log.insert(0, log_in)
                                        self.async_log(self.log_file, log_in)
                                        print(f"| [AGENT] {asset}: {agent_reason[:50]}... |")
                                        self.save_balance(); self.save_state()
                                else:
                                    # Output the reasoning why it was REJECTED/WAIT
                                    if iter_count % 5 == 0:
                                        print(f"| [AGENT] {asset}: {decision} | {agent_reason[:48]}... |")

                            # 3. Status Dashboard
                            n = len(self.positions[asset])
                            if n > 0:
                                cur_pnl = sum(((current_price / p['entry']) - 1) for p in self.positions[asset]) / n
                                sig_txt = f"ABERTO {n}x ({cur_pnl:+.2%})"
                                sig_ico = "B"
                            else:
                                sig_txt = f"COMPRA ({prob:.0%})" if signal == 1 else f"NEUTRO ({prob:.0%})"
                                sig_ico = "+" if signal == 1 else "."
                            print(f"|    {sig_ico} {asset:9}: {sig_txt:18} - {reason:18} |")
                    except Exception as e: print(f"Erro {asset}: {e}")

                list(self.executor.map(process_asset, self.assets))

                # XAUT/BTC (Integrado no ALPHA)
                try:
                    lines = self._process_xaut(timestamp)
                    for l in lines: print(l.encode('ascii', 'ignore').decode('ascii'))
                except Exception as e: print(f"[XAUT] Erro: {e}")

                print(f"+{'-'*72}+")

                self.history_log = self.history_log[:5]
                print(f"| # LOG RECENTE:                                                        |")
                for entry in self.history_log: print(f"| > {entry.encode('ascii', 'ignore').decode('ascii'):68} |")
                print(f"+{'-'*72}+")
                
            except Exception as e: print(f"Error Loop: {e}")
            iter_count += 1
            if iter_count % 2880 == 0:
                for rt in self.assets:
                    dfrt = self.engine.fetch_binance_klines(rt, limit=1500)
                    if not dfrt.empty:
                        dfrt = self.engine.apply_indicators(dfrt)
                        sc = self.brains[rt].train(dfrt, train_full=False, tp=self.take_profit, sl=self.stop_loss)
                        self.stats[rt]["oos_score"] = sc
            time.sleep(30)

if __name__ == "__main__":
    bot = MulticoreMasterBot()
    bot.run()
