# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
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
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET

load_dotenv()

# Import custom modules
from data.data_engine import DataEngine
from logic.basis_logic import BasisLogic
from logic.ml_brain import MLBrain
from logic.order_flow_logic import OrderFlowLogic
from logic.xaut_logic import XAUTAnalyzer
from logic.market_memory import MarketMemory
from logic.strategist_agent import StrategistAgent
from logic.usdt_brl_logic import UsdtBrlLogic
from logic.news_intelligence import NewsIntelligence
from logic.coingecko_client import CoinGeckoClient

# Forcar unbuffered stdout
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
        
        # Validar modo de execucao
        if self.live_mode:
            print("[SISTEMA] 🚨 MODO LIVE TRADING ATIVADO! Validando chaves API...")
            self._validate_api_keys()
        else:
            print("[SISTEMA] 🎮 Modo SIMULACAO (Paper Trading) Misto.")
        
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

        # ── TIER 3: Estrategia XAUT/BTC ──────────────────────────────────────
        # Agora o capital vem das posicoes abertas de BTCBRL
        self.xaut_max_positions   = int(os.getenv("XAUT_MAX_POSITIONS",      "3"))
        self.xaut_sl_pct          = float(os.getenv("XAUT_STOP_LOSS_PCT",    "0.02"))
        self.xaut_tp_pct          = float(os.getenv("XAUT_TAKE_PROFIT_PCT",  "0.04"))
        self.xaut_signal_threshold= 0.55 
        self.xaut_positions       = []     # Lista de posicoes abertas em XAUT
        self.xaut_pos_counter     = 0
        self.xaut_log             = "results/xaut_trades.txt"
        self.xaut_analyzer        = XAUTAnalyzer()
        self.xaut_lock            = Lock()
        self.xaut_history         = [] 

        # Macro Context
        self.last_sentiment = {"sentiment": "Neutral", "confidence": 0.5, "updated": ""}
        
        # Load Existing State
        self.usdt_balance = 0.0
        self.balance = self.load_balance()
        self.positions = self.load_state() 
        
        # Modules
        self.engine = DataEngine()
        self.basis_logic = BasisLogic()
        self.of_logic = OrderFlowLogic()
        self.usdt_logic = UsdtBrlLogic()
        
        # ML Brains
        self.brains = {asset: MLBrain() for asset in assets}
        self.agent = StrategistAgent() 
        self.news_intel = NewsIntelligence() # Global news sensor
        self.memory = MarketMemory() 
        self.cg_client = CoinGeckoClient()
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
                print("[ERRO FATAL] As chaves API nao tem permissao de Trading habilitada!")
                sys.exit(1)
            print("✅ Conectado na Binance! Permissao de leitura/trading ativa.")
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
        """Formata a fracao da ordem perfeitamente no stepSize obrigatorio da Binance para evitar falha no envio."""
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
                    self.usdt_balance = data.get("usdt_balance", 0.0)
                    self.last_sentiment = data.get("sentiment", self.last_sentiment)
                    # Restaurar posicoes XAUT/BTC
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
                    "usdt_balance": self.usdt_balance,
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
    # TIER 3 — Estrategia XAUT/BTC
    # ─────────────────────────────────────────────────────────────────────────

    def _process_usdt(self, timestamp: str) -> list:
        """
        Processa a logica de USDT/BRL (Porto Seguro e Media Reversao).
        """
        display_lines = []
        df_usdt = self.engine.fetch_usdt_brl_data(limit=300)
        if df_usdt.empty:
            display_lines.append("| [USDT/BRL] Sem dados disponiveis — aguardando...            |")
            return display_lines

        last_row = df_usdt.iloc[-1]
        current_price = float(last_row['close'])
        rsi_usdt = float(last_row.get('rsi', 50))
        
        # 1. Obter sinal da logica
        macro_summary = self.agent.intel.get_summary()
        macro_risk = macro_summary['risk_score']
        signal, confidence, reason = self.usdt_logic.get_signal(df_usdt, macro_risk)
        
        # 2. Validar com Agente Estrategista
        decision, agent_reason = self.agent.assess_usdt_opportunity(signal, confidence, reason)
        
        if decision == "APPROVE":
            if signal == 1: # COMPRAR USDT com BRL
                # Alocacao: 30% do saldo BRL ou trade_amount (o que for maior, respeitando limite)
                amount_to_spend = max(self.balance * 0.3, self.trade_amount)
                if self.balance >= amount_to_spend:
                    qty_usdt = amount_to_spend / current_price
                    if self.live_mode and self.client:
                        try:
                            exec_qty = self.format_quantity("USDTBRL", qty_usdt)
                            self.client.create_order(symbol="USDTBRL", side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=exec_qty)
                        except Exception as e:
                            print(f"[USDT] Erro compra: {e}"); return display_lines
                    
                    self.balance -= amount_to_spend
                    self.usdt_balance += qty_usdt
                    log_msg = f"[{timestamp}] COMPRA USDT: {agent_reason} | Preco: {current_price:.2f} | Qtd: {qty_usdt:.2f}"
                    self.history_log.insert(0, log_msg)
                    self.async_log(self.log_file, log_msg)
                    self.save_balance(); self.save_state()
            
            elif signal == -1: # VENDER USDT para BRL
                if self.usdt_balance > 0:
                    amount_to_receive = self.usdt_balance * current_price
                    if self.live_mode and self.client:
                        try:
                            exec_qty = self.format_quantity("USDTBRL", self.usdt_balance)
                            self.client.create_order(symbol="USDTBRL", side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=exec_qty)
                        except Exception as e:
                            print(f"[USDT] Erro venda: {e}"); return display_lines
                    
                    self.balance += amount_to_receive * (1 - self.fee_rate)
                    log_msg = f"[{timestamp}] VENDA USDT: {agent_reason} | Preco: {current_price:.2f} | BRL Recup: {amount_to_receive:.2f}"
                    self.usdt_balance = 0.0
                    self.history_log.insert(0, log_msg)
                    self.async_log(self.log_file, log_msg)
                    self.save_balance(); self.save_state()

        # Dashboard Lines
        sig_icon = "+" if signal == 1 else ("-" if signal == -1 else ".")
        display_lines.append(f"| [USDT/BRL] Preco: {current_price:5.2f} | RSI: {rsi_usdt:4.1f} | Saldo: {self.usdt_balance:8.2f} USDT |")
        if decision == "APPROVE" or confidence > 0.4:
            display_lines.append(f"|    {sig_icon} Sinal: {reason[:30]:30} | Status: {decision:8} |")
        
        return display_lines

    def _process_xaut(self, timestamp: str) -> list:
        display_lines = []

        # 1. Busca estoque de BTC disponivel do ALPHA (BTCBRL)
        with self.pos_lock:
            # Pega a lista de BTC de todas as posicoes abertas de BTCBRL
            btc_pos_list = self.positions.get('BTCBRL', [])
            if not isinstance(btc_pos_list, list):
                # Retrocompatibilidade: se for dict unico, converte para lista
                btc_pos_list = [btc_pos_list] if btc_pos_list else []
                self.positions['BTCBRL'] = btc_pos_list
            
            total_btc_holdings = sum(p['qty'] for p in btc_pos_list)
            # Reservamos o BTC que ja esta em XAUT (nao podemos gastar 2x)
            btc_in_xaut = sum(p['cost_btc'] for p in self.xaut_positions)
            available_btc = total_btc_holdings - btc_in_xaut

        # 2. Busca dados do ratio
        df_xaut = self.engine.fetch_xaut_ratio(limit=300)
        if df_xaut.empty:
            display_lines.append("| [XAUT/BTC] Sem dados disponiveis — aguardando...            |")
            return display_lines

        last_row      = df_xaut.iloc[-1]
        current_ratio = float(last_row['close'])
        rsi_ratio     = float(last_row.get('ratio_rsi', 50))
        bb_pct        = float(last_row.get('bb_pct', 0.5))

        signal, confidence, reason = self.xaut_analyzer.get_signal(df_xaut)

        closed_this_cycle = []

        with self.xaut_lock:
            # ── 2. Gerenciar posicoes abertas ────────────────────────────
            remaining = []
            for pos in self.xaut_positions:
                pos['current_ratio'] = current_ratio
                pnl_pct = self.xaut_analyzer.calc_pnl_pct(pos, current_ratio)
                pnl_btc = self.xaut_analyzer.calc_pnl_btc(pos, current_ratio)

                exit_reason = None
                if pnl_pct >= self.xaut_tp_pct:
                    exit_reason = "TAKE PROFIT"
        # 3. Gerenciamento de Posicoes (Saidas em BTC)
        closed_this_cycle = []
        with self.xaut_lock:
            remaining = []
            for pos in self.xaut_positions:
                pnl_pct = self.xaut_analyzer.calc_pnl_pct(pos, current_ratio)
                
                exit_reason = None
                if pnl_pct >= self.xaut_tp_pct: exit_reason = "TAKE PROFIT"
                elif pnl_pct <= -self.xaut_sl_pct: exit_reason = "STOP LOSS"

                if exit_reason:
                    # Calcula PnL liquido (taxa estimada 0.2%)
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

        # 4. Abertura de Novas Posicoes (Vendas de BTC -> XAUT)
        # (Signal, confidence e reason ja foram calculados acima na linha 285)
        
        # Tamanho fixo de aporte de BTC (aprox R$ 333 por slot se R$ 1000 total)
        # 0.0009 BTC e o valor real solicitado (3 posicoes de 0.0009 = 0.0027 BTC)
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

        # Recortar historico de display
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
                
                # 0. MACRO ANALYSIS (Agentic Layer)
                macro_data = self.engine.fetch_macro_data()
                news_sent  = self.news_intel.get_sentiment_score()
                self.btc_dominance = self.cg_client.get_btc_dominance()
                
                self.macro_risk = self.agent.radar.get_macro_score(
                    macro_data.get('dxy_change', 0), 
                    macro_data.get('sp500_change', 0), 
                    news_sent
                )
                macro_mult, macro_msg = self.agent.radar.get_recommended_position_mult()
                
                # Salva estado no inicio do loop
                self.save_state()
                
                # Fetch Real Balance if Live
                if self.live_mode:
                    self.balance = self.get_real_balance('BRL')
                    self.usdt_balance = self.get_real_balance('USDT')
                
                # 1. Calculo de Equity Total (Saldo + Valor de Mercado de todas as posicoes)
                total_equity = self.balance
                # Add USDT value to equity
                try:
                    usdt_price = float(self.client.get_symbol_ticker(symbol="USDTBRL")['price']) if self.live_mode else 5.0
                    total_equity += self.usdt_balance * usdt_price
                except: total_equity += self.usdt_balance * 5.0

                with self.pos_lock:
                    for p_asset, p_list in self.positions.items():
                        plist = p_list if isinstance(p_list, list) else ([p_list] if p_list else [])
                        for p_pos in plist:
                            p_pnl_pct = ((p_pos.get('current_price', p_pos['entry']) / p_pos['entry']) - 1) * p_pos['signal']
                            total_equity += p_pos.get('cost', self.trade_amount) * (1 + p_pnl_pct)

                print(f"""+--------------------------------------------------------------------------------+
| >>> ADVANCED MULTICORE BTC BOT | {timestamp} | Equity: R$ {total_equity:9.2f} |
| Saldo Disponivel: R$ {self.balance:8.2f}  | USDT: {self.usdt_balance:10.2f}              |
| Macro Risk Score: {self.macro_risk:6.2f}    | Recommendation: {macro_msg:<31} |
+--------------------------------------------------------------------------------+""")
                self.async_log(self.log_file, f"[{timestamp}] [UPTIME] {uptime_str} | Equity: R$ {total_equity:.2f}")
                self.total_equity = total_equity
                
                # Track equity history for dashboard (capped at 100 points)
                self.equity_history.append({
                    "time": timestamp,
                    "equity": round(total_equity, 2)
                })
                if len(self.equity_history) > 100: self.equity_history.pop(0)
                # TIER 1: PORTFOLIO
                if self.positions or self.usdt_balance > 0.01:
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
                        
                        # Mostrar USDT separadamente se houver saldo
                        if self.usdt_balance > 0.01:
                            try:
                                u_price = float(self.client.get_symbol_ticker(symbol="USDTBRL")['price']) if self.live_mode else 5.20
                            except: u_price = 5.20
                            u_val = self.usdt_balance * u_price
                            print(f"|    USDTBRL   : {self.usdt_balance:10.6f} COMPRA | Valor: R$ {u_val:8.2f} | PnL:  0.00% |")
                    print(f"+--------------------------------------------------------------------------------+")

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

                # TIER 1.5: USDT/BRL
                try:
                    lines_usdt = self._process_usdt(timestamp)
                    for l in lines_usdt: print(l)
                    print(f"+{'-'*72}+")
                except Exception as e:
                    import traceback
                    print(f"[USDT] Erro Loop: {e}")
                    traceback.print_exc()

                # TIER 2: ALPHA ML
                print(f"| [ALPHA ML ] Sinais baseados em Order Flow & ML:                       |")
                
                all_signals = {'tier1': curr_y / 100}
                asset_signals = {}
                signals_lock = threading.Lock()
                
                def process_asset(asset):
                    try:
                        df_ml = self.engine.fetch_binance_klines(asset, limit=300)
                        if df_ml.empty: return
                        df_ml = self.engine.apply_indicators(df_ml)
                        df_ml['macro_risk'] = self.macro_risk
                        df_ml['btc_dominance'] = self.btc_dominance
                        
                        processed_ml = self.brains[asset].prepare_features(df_ml)
                        feature_cols = [c for c in processed_ml.columns if c.startswith('feat_')]
                        last_features = processed_ml[feature_cols].values[-1]
                        
                        signal, prob, reason = self.brains[asset].predict_signal(last_features, feature_cols)
                        current_price = df_ml['close'].values[-1]
                        
                        with signals_lock:
                            asset_signals[asset] = {'signal': signal, 'prob': prob, 'reason': reason, 'price': current_price}
                        
                        print(f"|    {asset:7}: {signal:2} | Prob: {prob:5.1%} | {reason:<30} |")
                    except Exception as e: print(f"|    {asset:7}: ERRO -> {e}")

                # 1. SCAN (Parallel)
                list(self.executor.map(process_asset, self.assets))
                
                # 2. STRATEGIST AGENT DECISION (LangGraph)
                tier2_agg = sum([s['signal'] for s in asset_signals.values()])
                all_signals['tier2'] = tier2_agg
                
                # Enriquecer macro_data com sentimento para o Agente (Neo4j)
                macro_data['news_sentiment'] = news_sent
                agent_res = self.agent.run(all_signals, macro_data)
                
                # Log thinking
                self.async_log("results/agent_thinking.log", f"[{timestamp}] {json.dumps(agent_res['reasoning'])}")
                final_mult = agent_res['allocation_mult']
                print(f"| [STRATEGIST] Decisao: {agent_res['decision']} | Mult: {final_mult:.2f} |")
                print(f"+--------------------------------------------------------------------------------+")

                # 3. EXECUTION (Sequential)
                for asset, s_data in asset_signals.items():
                    try:
                        signal = s_data['signal']
                        current_price = s_data['price']
                        prob = s_data['prob']
                        reason = s_data['reason']

                        # --- A. Position Management (Exits) ---
                        active_pos = self.positions.get(asset, [])
                        if not isinstance(active_pos, list):
                            active_pos = [active_pos] if active_pos else []
                        
                        remaining = []
                        for pos in active_pos:
                            pos['current_price'] = current_price
                            pnl = ((current_price / pos['entry']) - 1) * pos['signal']
                            exit_reason = None
                            
                            # Use dynamic TP/SL
                            current_tp = self.take_profit * pos.get('tp_mult', 1.0)
                            current_sl = self.stop_loss * pos.get('sl_mult', 1.0)
                            
                            if pnl > self.trailing_activation:
                                if 'max_pnl' not in pos: pos['max_pnl'] = pnl
                                else: pos['max_pnl'] = max(pos['max_pnl'], pnl)
                                if pnl < (pos['max_pnl'] - self.trailing_callback):
                                    exit_reason = f"TRAILING STOP ({pos['max_pnl']:.2%})"
                            
                            if not exit_reason:
                                if pnl >= current_tp: exit_reason = "TAKE PROFIT"
                                elif pnl <= -current_sl: exit_reason = "STOP LOSS"
                                elif signal == -pos['signal'] and prob >= 0.75: exit_reason = "REVERSAL"

                            if exit_reason:
                                if asset == "BTCBRL": # Cascade Exit for XAUT
                                    with self.xaut_lock:
                                        self.xaut_positions = [] # Simplified for demo
                                
                                if self.live_mode and self.client:
                                    try:
                                        exec_qty = self.format_quantity(asset, pos['qty'])
                                        self.client.create_order(symbol=asset, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=exec_qty)
                                    except Exception as e: print(f"Erro fechar {asset}: {e}"); remaining.append(pos); continue

                                net_pnl = pnl - (self.fee_rate * 2)
                                self.balance += pos['cost'] * (1 + net_pnl)
                                self.memory.record_outcome(net_pnl)
                                log_out = f"[{timestamp}] FECHADO {asset}: {exit_reason} | PnL: {net_pnl:+.2%} | BRL: {self.balance:.2f}"
                                self.history_log.insert(0, log_out)
                                self.save_balance()
                            else:
                                remaining.append(pos)
                        self.positions[asset] = remaining

                        # --- B. Entries & DCA (Decision Gate) ---
                        max_dca = 2 if asset == "BTCBRL" else 1
                        if signal != 0 and len(self.positions[asset]) < max_dca:
                            decision, agent_reason, smodifiers = self.agent.assess_trade(asset, signal, prob, reason)
                            
                            if decision == "APPROVE" and (agent_res['decision'] == "EXECUTE_ALPHA" or signal == 0):
                                current_trade_size = (self.balance * self.risk_per_trade_pct) * (final_mult * smodifiers['size_mult'])
                                
                                if self.balance >= current_trade_size and current_trade_size >= self.min_binance_amount:
                                    qty = current_trade_size / current_price
                                    entry_p = current_price
                                    if self.live_mode and self.client:
                                        try:
                                            exec_qty = self.format_quantity(asset, qty)
                                            self.client.create_order(symbol=asset, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=exec_qty)
                                        except Exception as e: print(f"Erro abrir {asset}: {e}"); continue

                                    self.positions[asset].append({
                                        "entry": entry_p, "signal": signal, "qty": qty, "cost": current_trade_size,
                                        "time": timestamp, "current_price": entry_p,
                                        "tp_mult": smodifiers['tp_mult'], "sl_mult": smodifiers['sl_mult']
                                    })
                                    self.balance -= current_trade_size
                                    log_in = f"[{timestamp}] ABERTO {asset} ({smodifiers['size_mult']}x): @ {entry_p:.2f} | BRL: {self.balance:.2f}"
                                    self.history_log.insert(0, log_in)
                                    self.save_balance(); self.save_state()
                                    print(f"| [AGENT] {asset}: {agent_reason[:50]}... |")
                            else:
                                if iter_count % 10 == 0:
                                    print(f"| [FILTRO] {asset}: {decision} | {agent_reason[:48]}... |")

                    except Exception as e: print(f"Erro processando {asset}: {e}")

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
