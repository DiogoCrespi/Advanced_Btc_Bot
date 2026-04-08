# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import time
import os
import sys
import orjson as json
import requests
import queue
import threading
import argparse
import numpy as np
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from threading import Lock, Thread
# removed: fastapi, uvicorn imports

import math
from dotenv import load_dotenv
from binance.client import AsyncClient
from binance import BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from logic.execution import BinanceLive, BinanceTestnet, BacktestEngine

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
from logic.mirofish_client import MiroFishClient
from logic.coingecko_client import CoinGeckoClient
from logic.risk_manager import RiskManager

# Forcar unbuffered stdout
sys.stdout.reconfigure(line_buffering=True)

def orjson_default(obj):
    """ Custom encoder default for numpy data types with orjson """
    if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                        np.int16, np.int32, np.int64, np.uint8,
                        np.uint16, np.uint32, np.uint64)):
        return int(obj)
    elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    raise TypeError(f"Type {type(obj)} not serializable")

class MulticoreMasterBot:
    def __init__(self, assets=["BTCBRL", "ETHBRL", "SOLBRL"], cofre_threshold=0.08, mode="backtest"):
        self.mode = mode
        self.live_mode = (mode == "live")
        
        self.assets = assets
        self.cofre_threshold = cofre_threshold
        self.history_log = [] 
        self.log_file = "results/signals_log.txt"
        self.status_file = "results/bot_status.json"
        self.start_time = datetime.now()  # Uptime tracking
        self.equity_history = [] # For dashboard charts
        
        # Initialize Exchange interface based on mode
        if self.mode == "live":
            print("[SISTEMA] 🚨 MODO LIVE TRADING ATIVADO!")
            self.exchange = BinanceLive()
        elif self.mode == "testnet":
            print("[SISTEMA] 🧪 MODO TESTNET ATIVADO!")
            self.exchange = BinanceTestnet()
        elif self.mode == "backtest":
            print("[SISTEMA] 🎮 Modo BACKTEST (Simulacao Local) ATIVADO.")
            self.exchange = BacktestEngine(initial_balance=1000.0)
        else:
            print(f"[ERRO] Modo de execucao invalido: {self.mode}")
            sys.exit(1)
        
        self.trade_amount = 100.0   # Base fallback
        self.risk_per_trade_pct = 0.05 # 5% per trade
        self.fee_rate = 0.001       # 0.1% Binance Standard

        # Note: Risk is now handled dynamically by self.risk_manager.
        # Keeping variables below for legacy references / internal ML Brain defaults.
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
        self.miro_client = MiroFishClient() # MiroFish AI Agent Swarm
        self.miro_sim_id = "live_bot_sim"
        self.ntfy_topic = os.getenv("NTFY_TOPIC", "btc_bot_trades")
        self.ntfy_url = "http://ntfy" # Docker internal hostname
        # Garante que a simulação existe
        self.miro_client.create_simulation("auto_live", self.miro_sim_id)
        self.miro_client.start_simulation(self.miro_sim_id)
        self.memory = MarketMemory() 
        self.cg_client = CoinGeckoClient()
        self.stats = {asset: {"history_days": 0, "samples": 0, "oos_score": 0.0} for asset in assets}
        
        # Risk Manager Configuration
        self.risk_manager = RiskManager()

        # Async I/O Logging Queue
        self.log_queue = queue.Queue()
        self.log_thread = Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()
        
        # Lock for thread-safe position updates
        self.pos_lock = Lock()

        # High-Speed WebSocket Multiplexing State
        self.live_prices = {}
        self.stream_queue = asyncio.Queue()
        self.last_ws_message_time = time.time()

        # Thread Pool Executor (Persistent) for sync io / legacy code
        self.executor = ThreadPoolExecutor(max_workers=len(self.assets))
        self.process_executor = ProcessPoolExecutor(max_workers=len(self.assets))
        
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
        
    def notify_ntfy(self, message, title="BTC BOT UPDATE"):
        """Envia notificacao push via ntfy (Docker Net)"""
        try:
            if not self.ntfy_topic:
                return
            url = f"{self.ntfy_url}/{self.ntfy_topic}"
            tags = "shopping_cart" if "ABERTO" in message else "heavy_dollar_sign"
            priority = "high" if "ABERTO" in message else "default"
            
            requests.post(url, 
                         data=message.encode('utf-8'),
                         headers={
                             "Title": title,
                             "Priority": priority,
                             "Tags": tags
                         },
                         timeout=5)
        except Exception as e:
            print(f"[NOTIFY] Erro ao enviar notificacao: {e}")

    async def get_real_balance_async(self, asset='BRL'):
        """Retorna o saldo real (Free Balance) da carteira Spot via Exchange Interface (Assincrono)."""
        try:
            return await self.exchange.get_balance(asset)
        except Exception:
            return self.balance # fallback

    @property
    def client(self):
        """Helper to access the internal binance client for legacy/websocket hooks."""
        return getattr(self.exchange, 'client', None)
            
    async def format_quantity_async(self, asset, raw_qty):
        """Formata a fracao da ordem perfeitamente no stepSize obrigatorio da Binance para evitar falha no envio."""
        try:
            info = await self.exchange.get_symbol_info(asset)
            if info:
                step_size = None
                for f in info['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = float(f['stepSize'])
                        break
                if step_size:
                    precision = int(round(-math.log(step_size, 10), 0))
                    return math.floor(raw_qty * (10**precision)) / (10**precision)
        except Exception: pass
        return round(raw_qty, 5)

    async def _process_stream(self):
        """Consume multiplexed websocket messages to maintain real-time states."""
        while True:
            msg = await self.stream_queue.get()
            self.last_ws_message_time = time.time()
            if not msg:
                continue

            try:
                # Handle multiplexed payloads
                if 'data' in msg and 'stream' in msg:
                    stream_name = msg['stream']
                    data = msg['data']

                    if 'e' in data and data['e'] == '24hrTicker':
                        symbol = data['s']
                        self.live_prices[symbol] = float(data['c'])
                elif 'e' in msg and msg['e'] == '24hrTicker':
                     symbol = msg['s']
                     self.live_prices[symbol] = float(msg['c'])

            except Exception as e:
                print(f"[STREAM ERROR] Error processing message: {e}")
            finally:
                self.stream_queue.task_done()

    async def _start_multiplex_socket(self):
        """Initialize the BinanceSocketManager multiplex stream."""
        if not self.client:
            return

        bsm = BinanceSocketManager(self.client)
        streams = [f"{asset.lower()}@ticker" for asset in self.assets]
        streams.append("usdtbrl@ticker")

        async with bsm.multiplex_socket(streams) as ms:
            print(f"[WEBSOCKET] Conectado aos streams: {streams}")
            while True:
                try:
                    res = await ms.recv()
                    await self.stream_queue.put(res)
                except Exception as e:
                    print(f"[WEBSOCKET ERROR] Connection dropped: {e}")
                    break

    async def _monitor_heartbeat(self):
        """Monitors WS connection health and triggers silent reconnects."""
        while True:
            await asyncio.sleep(10)
            if time.time() - self.last_ws_message_time > 30:
                print("[HEARTBEAT] WebSocket timeout excedido (>30s). Tentando reconectar...")
                # Note: For robust reconnections, we'd cancel the current socket task and restart it.
                # Here we simulate by just logging it for now, relying on the loop inside ms.recv to break on real drop.
                self.last_ws_message_time = time.time() # Reset to avoid spam

    def load_balance(self):
        if os.path.exists(self.balance_file):
            try:
                with open(self.balance_file, "r") as f:
                    return float(f.read().strip())
            except Exception: pass
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
                    with open(filepath, "wb") as f:
                        f.write(json.dumps(state_data, default=orjson_default, option=json.OPT_INDENT_2))
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
                with open(self.status_file, "rb") as f:
                    data = json.loads(f.read())
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

        current_price = float(df_usdt['close'].values[-1])
        rsi_usdt = float(df_usdt['rsi'].values[-1]) if 'rsi' in df_usdt.columns else 50.0
        
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
                    if self.mode != "backtest":
                        try:
                            exec_qty = self.format_quantity("USDTBRL", qty_usdt)
                            self.exchange.create_order(symbol="USDTBRL", side=SIDE_BUY, order_type=ORDER_TYPE_MARKET, quantity=exec_qty)
                        except Exception as e:
                            print(f"[USDT] Erro compra: {e}"); return display_lines
                    elif self.mode == "backtest":
                        # In backtest mode, simulate execution logic internally
                        pass
                    
                    self.balance -= amount_to_spend
                    self.usdt_balance += qty_usdt
                    log_msg = f"[{timestamp}] COMPRA USDT: {agent_reason} | Preco: {current_price:.2f} | Qtd: {qty_usdt:.2f}"
                    self.history_log.insert(0, log_msg)
                    self.async_log(self.log_file, log_msg)
                    self.save_balance(); self.save_state()
            
            elif signal == -1: # VENDER USDT para BRL
                if self.usdt_balance > 0:
                    amount_to_receive = self.usdt_balance * current_price
                    if self.mode != "backtest":
                        try:
                            exec_qty = self.format_quantity("USDTBRL", self.usdt_balance)
                            self.exchange.create_order(symbol="USDTBRL", side=SIDE_SELL, order_type=ORDER_TYPE_MARKET, quantity=exec_qty)
                        except Exception as e:
                            print(f"[USDT] Erro venda: {e}"); return display_lines
                    elif self.mode == "backtest":
                        pass
                    
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

        current_ratio = float(df_xaut['close'].values[-1])
        rsi_ratio     = float(df_xaut['ratio_rsi'].values[-1]) if 'ratio_rsi' in df_xaut.columns else 50.0
        bb_pct        = float(df_xaut['bb_pct'].values[-1]) if 'bb_pct' in df_xaut.columns else 0.5

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

    async def run_async(self):
        print(f"Iniciando Loop de Execucao (Intervalo: 30s)")
        print(f"[UPTIME] Bot iniciado em: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        iter_count = 0
        while True:
            try:
                timestamp = datetime.now().strftime('%H:%M:%S')
                uptime_str = self._get_uptime_str()
                
                # 0. MACRO ANALYSIS (Agentic Layer)
                # Fetching external API data concurrently
                loop = asyncio.get_running_loop()
                macro_data_task = loop.run_in_executor(self.executor, self.engine.fetch_macro_data)
                miro_data_task = loop.run_in_executor(self.executor, self.miro_client.get_sentiment_summary, self.miro_sim_id)
                btc_dom_task = loop.run_in_executor(self.executor, self.cg_client.get_btc_dominance)

                macro_data, miro_data, self.btc_dominance = await asyncio.gather(
                    macro_data_task, miro_data_task, btc_dom_task
                )
                
                m_sent = miro_data['sentiment']
                m_conf = miro_data['confidence']
                if m_sent == "Bullish": news_sent = m_conf
                elif m_sent == "Bearish": news_sent = -m_conf
                else: news_sent = 0.0
                print(f"[MIROFISH] Analise de Sentimento Profundo: {m_sent} ({m_conf*100:.1f}%) | Score: {news_sent:.2f}")
                
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
                    self.balance = await self.get_real_balance_async('BRL')
                    self.usdt_balance = await self.get_real_balance_async('USDT')
                
                # 1. Calculo de Equity Total (Saldo + Valor de Mercado de todas as posicoes)
                total_equity = self.balance
                # Add USDT value to equity
                try:
                    # Prefer live prices if available from WS
                    if "USDTBRL" in self.live_prices:
                        usdt_price = self.live_prices["USDTBRL"]
                    else:
                        ticker = await self.exchange.get_ticker(symbol="USDTBRL")
                        usdt_price = float(ticker['price']) if ticker else 5.0
                    total_equity += self.usdt_balance * usdt_price
                except Exception: total_equity += self.usdt_balance * 5.0

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

                # Check Max Drawdown limit
                self.risk_manager.update_equity_high(total_equity)
                if self.risk_manager.check_max_drawdown(total_equity):
                    print("[ALERTA] Limite Max Drawdown atingido! Cooldown ativado.")

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
                                if "USDTBRL" in self.live_prices:
                                    u_price = self.live_prices["USDTBRL"]
                                else:
                                    ticker = await self.exchange.get_ticker(symbol="USDTBRL")
                                    u_price = float(ticker['price']) if ticker else 5.20
                            except Exception: u_price = 5.20
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
                
                async def async_process_asset(asset):
                    try:
                        # Offload IO to executor
                        loop = asyncio.get_running_loop()
                        df_ml = await loop.run_in_executor(self.executor, self.engine.fetch_binance_klines, asset, "1h", 300)
                        if df_ml.empty: return

                        df_ml = await loop.run_in_executor(self.executor, self.engine.apply_indicators, df_ml)
                        df_ml['macro_risk'] = self.macro_risk
                        df_ml['btc_dominance'] = self.btc_dominance
                        
                        # Pre-process minimal state locally to avoid pickling the whole Brain/Bot
                        df_ml['macro_risk'] = self.macro_risk
                        df_ml['btc_dominance'] = self.btc_dominance

                        # Fetch the brain instance (the brain model itself is usually pickleable
                        # if it's just an sklearn model and basic variables)
                        brain_instance = self.brains[asset]
                        
                        signal, prob, reason, current_price = await loop.run_in_executor(
                            self.process_executor,
                            _cpu_heavy_predict,
                            brain_instance, df_ml
                        )
                        
                        with signals_lock:
                            asset_signals[asset] = {'signal': signal, 'prob': prob, 'reason': reason, 'price': current_price}
                        
                        print(f"|    {asset:7}: {signal:2} | Prob: {prob:5.1%} | {reason:<30} |")
                    except Exception as e: print(f"|    {asset:7}: ERRO -> {e}")

                # 1. SCAN (Parallel with Asyncio)
                await asyncio.gather(*(async_process_asset(asset) for asset in self.assets))
                
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
                            
                            # ML Signal logic
                            ml_signal_str = 'HOLD'
                            if signal == -pos['signal'] and prob >= 0.75:
                                ml_signal_str = 'REVERSAL'

                            pos_id = pos.get('id', f"{pos['time']}_{pos['entry']}")
                            
                            # Intercept with Risk Manager
                            action, risk_reason = self.risk_manager.check_exit_conditions(
                                asset=asset,
                                pos_id=pos_id,
                                current_price=current_price,
                                entry_price=pos['entry'],
                                signal_direction=pos['signal'],
                                ml_signal=ml_signal_str
                            )

                            if action == 'SELL' or risk_reason:
                                exit_reason = risk_reason or action
                            elif ml_signal_str == 'REVERSAL':
                                exit_reason = "REVERSAL"

                            if exit_reason:
                                self.risk_manager.cleanup_tracking(asset, pos_id)
                                if asset == "BTCBRL": # Cascade Exit for XAUT
                                    with self.xaut_lock:
                                        self.xaut_positions = [] # Simplified for demo
                                
                                if self.mode != "backtest":
                                    try:
                                        exec_qty = await self.format_quantity_async(asset, pos['qty'])
                                        await self.exchange.create_order(symbol=asset, side=SIDE_SELL, order_type=ORDER_TYPE_MARKET, quantity=exec_qty)
                                    except Exception as e: print(f"Erro fechar {asset}: {e}"); remaining.append(pos); continue
                                elif self.mode == "backtest":
                                    pass

                                net_pnl = pnl - (self.fee_rate * 2)
                                self.balance += pos['cost'] * (1 + net_pnl)
                                self.memory.record_outcome(net_pnl)
                                log_out = f"[{timestamp}] FECHADO {asset}: {exit_reason} | PnL: {net_pnl:+.2%} | BRL: {self.balance:.2f}"
                                self.history_log.insert(0, log_out)
                                self.save_balance()
                                self.notify_ntfy(log_out, title=f"VENDA: {asset}")
                            else:
                                remaining.append(pos)
                        self.positions[asset] = remaining

                        # --- B. Entries & DCA (Decision Gate) ---
                        max_dca = 2 if asset == "BTCBRL" else 1

                        # Block new entries if in cooldown
                        in_cooldown = self.risk_manager.is_in_cooldown()

                        if signal != 0 and len(self.positions[asset]) < max_dca and not in_cooldown:
                            decision, agent_reason, smodifiers = self.agent.assess_trade(asset, signal, prob, reason)
                            
                            if decision == "APPROVE" and (agent_res['decision'] == "EXECUTE_ALPHA" or signal == 0):
                                current_trade_size = (self.balance * self.risk_per_trade_pct) * (final_mult * smodifiers['size_mult'])
                                
                                if self.balance >= current_trade_size and current_trade_size >= self.min_binance_amount:
                                    qty = current_trade_size / current_price
                                    entry_p = current_price
                                    if self.mode != "backtest":
                                        try:
                                            exec_qty = await self.format_quantity_async(asset, qty)
                                            await self.exchange.create_order(symbol=asset, side=SIDE_BUY, order_type=ORDER_TYPE_MARKET, quantity=exec_qty)
                                        except Exception as e: print(f"Erro abrir {asset}: {e}"); continue
                                    elif self.mode == "backtest":
                                        pass

                                    self.positions[asset].append({
                                        "entry": entry_p, "signal": signal, "qty": qty, "cost": current_trade_size,
                                        "time": timestamp, "current_price": entry_p,
                                        "tp_mult": smodifiers['tp_mult'], "sl_mult": smodifiers['sl_mult']
                                    })
                                    self.balance -= current_trade_size
                                    log_in = f"[{timestamp}] ABERTO {asset} ({smodifiers['size_mult']}x): @ {entry_p:.2f} | BRL: {self.balance:.2f}"
                                    self.history_log.insert(0, log_in)
                                    self.save_balance(); self.save_state()
                                    self.notify_ntfy(log_in, title=f"COMPRA: {asset}")
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
            await asyncio.sleep(30)

async def main(bot):
    if bot.mode != "backtest" and hasattr(bot.exchange, 'initialize'):
        await bot.exchange.initialize()

    # Start tasks
    stream_task = asyncio.create_task(bot._process_stream())
    ws_task = asyncio.create_task(bot._start_multiplex_socket())
    heartbeat_task = asyncio.create_task(bot._monitor_heartbeat())
    main_loop_task = asyncio.create_task(bot.run_async())

    await asyncio.gather(main_loop_task, stream_task, ws_task, heartbeat_task)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Advanced Multicore BTC Bot')
    parser.add_argument('--mode', type=str, choices=['live', 'testnet', 'backtest'], default='backtest',
                        help='Execution mode: live, testnet, or backtest (default)')
    args = parser.parse_args()

    bot = MulticoreMasterBot(mode=args.mode)
    
    # Run the async main entry point
    asyncio.run(main(bot))
