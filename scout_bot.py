import math
import logging
import asyncio
import os
import json
import socket
import time
import argparse
import requests
import gc
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from threading import Thread, Lock
import queue
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from collections import deque

# Local Dependencies
from logic.execution.binance_live import BinanceLive
from logic.execution.binance_testnet import BinanceTestnet
from logic.execution.backtest_engine import BacktestEngine
from logic.execution.limit_executor import LimitExecutor
from logic.feature_store import FeatureStore
from logic.ml_brain import MLBrain
from logic.order_flow_logic import OrderFlowLogic
from logic.risk_manager import RiskManager
from logic.strategist_agent import StrategistAgent
from logic.market_memory import MarketMemory
from logic.local_oracle import LocalOracle
from logic.coingecko_client import CoinGeckoClient
from logic.evolutionary_engine import EvolutionaryEngine, DNA
from logic.xaut_logic import XAUTAnalyzer
from logic.tribunal import ConsensusTribunal
from data.data_engine import DataEngine
from logic.basis_logic import BasisLogic
from logic.usdt_brl_logic import UsdtBrlLogic
from logic.database.ledger import Ledger
from binance import BinanceSocketManager

# Logger Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ScoutBot")

# CONSTANTS
SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

def _cpu_heavy_predict(brain, df, macro_risk, btc_dom, threshold):
    """Encapsula a predição para ser rodada em ProcessPoolExecutor e evitar GIL."""
    return brain.predict(df, macro_risk, btc_dom, threshold)

class Watchdog:
    """Monitora a saúde das threads e loops assíncronos."""
    def __init__(self, bot, timeout=120):
        self.bot = bot
        self.timeout = timeout
        self.last_heartbeat = time.time()
        self._running = True

    def start(self):
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self._running:
            if time.time() - self.bot.last_tick > self.timeout:
                print(f"[WATCHDOG] LENTIDÃO DETECTADA: {time.time() - self.bot.last_tick:.1f}s sem tick!")
                # Em um ambiente real, poderiamos reiniciar o processo aqui
            time.sleep(30)

    def stop(self): self._running = False

class WebSocketSupervisor:
    """Gerencia a conexão persistente com a Binance via WebSocket."""
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("Supervisor")
        self._is_running = True
        self._backoff_delay = 1

    async def start(self):
        if self.bot.mode == "backtest":
            self.logger.info("Supervisor disabled (Backtest Mode)")
            return
        while self._is_running:
            try:
                await self._run_socket_session()
                self._backoff_delay = 1
            except Exception as e:
                self.logger.error(f"[SUPERVISOR] Queda critica: {e}")
                await self._handle_reconnection()

    async def _run_socket_session(self):
        if not self.bot.client:
            self.logger.warning("[SUPERVISOR] Binance Client nulo. Tentando inicializar em breve...")
            # Tenta inicializar se possível
            if hasattr(self.bot.exchange, 'initialize'):
                try:
                    await self.bot.exchange.initialize()
                except Exception as e:
                    self.logger.error(f"[SUPERVISOR] Falha ao inicializar client: {e}")
            await asyncio.sleep(10)
            return

        try:
            bm = BinanceSocketManager(self.bot.client)
            streams = [f"{s.lower()}@ticker" for s in self.bot.assets]
            if "usdtbrl@ticker" not in streams: streams.append("usdtbrl@ticker")
            
            user_socket = None
            if self.bot.listen_key:
                self.logger.info(f"[SUPERVISOR] Adicionando User Data Stream: {self.bot.listen_key[:10]}...")
                user_socket = bm.user_socket()

            self.logger.info(f"[SUPERVISOR] Iniciando Multiplex Socket para {len(streams)} streams...")
            
            if user_socket:
                async with bm.multiplex_socket(streams) as ms, user_socket as us:
                    while True:
                        done, pending = await asyncio.wait(
                            [ms.recv(), us.recv()],
                            return_when=asyncio.FIRST_COMPLETED,
                            timeout=30
                        )
                        for task in done:
                            res = task.result()
                            if res and 'data' in res:
                                data = res['data']; symbol = data['s']
                                self.bot.live_prices[symbol] = float(data['c'])
                            elif res and 'e' in res:
                                await self._handle_user_event(res)
                        self._backoff_delay = 1
            else:
                async with bm.multiplex_socket(streams) as stream:
                    while True:
                        res = await asyncio.wait_for(stream.recv(), timeout=30)
                        if res and 'data' in res:
                            data = res['data']; symbol = data['s']
                            self.bot.live_prices[symbol] = float(data['c'])
                        self._backoff_delay = 1
        except asyncio.TimeoutError:
            self.logger.warning("[SUPERVISOR] Timeout no WebSocket. Reiniciando...")
        except Exception as e:
            self.logger.error(f"[SUPERVISOR] Erro no socket: {e}")
            raise

    async def _handle_user_event(self, event):
        etype = event.get('e')
        if etype == 'outboundAccountPosition':
            self.logger.info("[SUPERVISOR] Atualizacao de Saldo via WebSocket detectada.")
            for balance in event.get('B', []):
                asset = balance.get('a')
                free = float(balance.get('f'))
                if asset == 'BRL': self.bot.balance = free
                elif asset == 'USDT': self.bot.usdt_balance = free
            self.bot.save_balance()
            self.bot.save_state()
        elif etype == 'balanceUpdate':
            self.logger.info(f"[SUPERVISOR] Balance Update: {event.get('a')} {event.get('d')}")
            self.bot.last_balance_sync = datetime.now() - timedelta(hours=1)

    async def _handle_reconnection(self):
        for s in self.bot.assets: self.bot.live_prices[s] = 0.0
        self.bot.live_prices["USDTBRL"] = 0.0
        wait_time = min(self._backoff_delay, 60)
        await asyncio.sleep(wait_time)
        self._backoff_delay *= 2

    def stop(self): self._is_running = False

class ScoutBot:
    def __init__(self, assets=["BTCBRL", "ETHBRL", "SOLBRL", "LINKBRL", "AVAXBRL", "RENDERBRL"], mode="backtest"):
        self.mode = mode
        self.live_mode = (mode == "live")
        self.assets = assets
        self.history_log = []
        self.log_file = "results/signals_log.txt"
        self.status_file = "results/bot_status.json"
        self.start_time = datetime.now()
        
        if self.mode == "live": self.exchange = BinanceLive()
        elif self.mode == "testnet": self.exchange = BinanceTestnet()
        else: self.exchange = BacktestEngine(initial_balance=1000.0)

        self.trade_amount = 10.0
        self.fee_rate = 0.001
        self.take_profit = 0.03
        self.stop_loss = 0.015
        self.min_binance_amount = 10.0
        self.balance_file = "results/balance_state.txt"
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        self.xaut_max_positions = 3
        self.xaut_positions = []
        self.xaut_pos_counter = 0
        self.xaut_log = "results/xaut_trades.txt"
        self.xaut_analyzer = XAUTAnalyzer()
        self.xaut_lock = Lock()
        self.xaut_history = []

        self.signal_history = {asset: deque(maxlen=1000) for asset in assets}
        self.safe_mode = False
        self.shadow_brains = {asset: MLBrain() for asset in assets}
        self.evo_engine = EvolutionaryEngine(population_size=5)
        self.evo_brains = {dna.id: {asset: MLBrain(dna=dna) for asset in assets} for dna in self.evo_engine.population}
        self.last_regime_metrics = {"volatility": 0.0, "trend": 0.0, "sentiment": 0.0}
        self.macro_risk = 0.5
        self.macro_status = {'is_extreme': False, 'reason': None}
        self.btc_dominance = 50.0

        self.tribunal = ConsensusTribunal()
        self.engine = DataEngine()
        self.basis_logic = BasisLogic()
        self.usdt_logic = UsdtBrlLogic()
        self.brains = {asset: MLBrain() for asset in assets}
        self.agent = StrategistAgent()
        self.memory = MarketMemory()
        self.oracle_state = {"sentiment": "Neutral", "confidence": 0.5, "multiplier": 1.0, "macro_risk": 0.5}
        self.oracle = LocalOracle(self.memory, self.oracle_state)
        self.cg_client = CoinGeckoClient()
        self.stats = {asset: {"oos_score": 0.0} for asset in assets}
        self.risk_manager = RiskManager()
        self.ledger = Ledger(db_path='results/scout_ledger.db')
        self.limit_executor = LimitExecutor(self.exchange)
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.use_mirofish = False
        self.listen_key = None
        self.last_balance_sync = datetime.now()
        self.shadow_mode = os.getenv("SHADOW_MODE", "True").lower() == "true"
        if self.shadow_mode:
            print("[BOOT] MODO SHADOW ATIVADO: Nenhuma ordem real sera enviada.")
        
        self.last_tick = time.time()
        self.watchdog = Watchdog(self)
        self.watchdog.start()
        
        self.caution_mode = False
        self.initial_equity = None
        self.check_caution_at = None

        self.log_queue = queue.Queue()
        self.log_thread = Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()
        self.pos_lock = Lock()
        self.live_prices = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.process_executor = ProcessPoolExecutor(max_workers=2)

        self.liquidity_mult = {"BTCBRL":1.0, "ETHBRL":0.95, "SOLBRL":0.85, "LINKBRL":0.8, "AVAXBRL":0.8, "RENDERBRL":0.75}
        saved_balance = self.ledger.get_last_balance()
        self.balance = saved_balance if saved_balance is not None else self.load_balance()
        self.positions = self.ledger.load_active_positions()
        if not self.positions: self.positions = self.load_state()
        
        self.total_equity = self.balance
        self.dashboard_logs = deque(maxlen=5)
        self.last_status_report = datetime.now() - timedelta(hours=3, minutes=55)
        
        print("[INIT] Booting Multicore Brains...")
        os.makedirs("models", exist_ok=True)
        for asset in assets:
            model_path = f"models/{asset.lower()}_brain_v1.pkl"
            if not self.brains[asset].load_model(model_path):
                print(f"[WARN] {asset}: Treinando v1 do zero...")
                df = self.engine.fetch_binance_klines(asset, limit=1000)
                if not df.empty:
                    df = self.engine.apply_indicators(df)
                    score = self.brains[asset].train(df, train_full=True, tp=self.take_profit, sl=self.stop_loss)
                    self.brains[asset].save_model(model_path)
                    self.stats[asset]["oos_score"] = score
            
            shadow_path = f"models/brain_rf_v3_alpha_{asset}.pkl"
            if not self.shadow_brains[asset].load_model(shadow_path):
                print(f"[WARN] {asset}: Shadow v3-Alpha nao encontrado.")

    def _log_worker(self):
        while True:
            item = self.log_queue.get()
            if item is None: break
            try:
                action, (path, content) = item
                if action == "append":
                    with open(path, "a", encoding="utf-8") as f: f.write(content + "\n")
                elif action == "write":
                    with open(path, "w", encoding="utf-8") as f: f.write(content)
                elif action == "save_state":
                    # Use standard json since orjson might not be available or needed here
                    with open(path, "w", encoding="utf-8") as f: json.dump(content, f, indent=2)
            except Exception: pass
            self.log_queue.task_done()

    def async_log(self, p, c): self.log_queue.put(("append", (p, c)))
    def save_balance(self):
        self.ledger.save_balance(self.balance, self.total_equity)
        self.log_queue.put(("write", (self.balance_file, f"{self.balance:.2f}")))
    def load_balance(self):
        if os.path.exists(self.balance_file):
            try: return float(open(self.balance_file).read().strip())
            except Exception: pass
        return 1000.0

    def load_state(self):
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r") as f:
                    s = json.load(f)
                    self.usdt_balance = s.get("usdt_balance", 0.0)
                    self.xaut_positions = s.get("xaut_positions", [])
                    self.caution_mode = s.get("caution_mode", False)
                    return s.get("positions", {})
            except Exception: pass
        self.usdt_balance = 0.0
        return {}

    def save_state(self):
        with self.pos_lock:
            rel_stats = {asset: {"samples": self.brains[asset].n_samples, "score": self.brains[asset].reliability_score} for asset in self.assets}
            st = {
                "balance": self.balance, 
                "usdt_balance": self.usdt_balance, 
                "positions": self.positions, 
                "xaut_positions": self.xaut_positions,
                "caution_mode": self.caution_mode,
                "reliability_stats": rel_stats
            }
        self.log_queue.put(("save_state", (self.status_file, st)))

    async def sync_balances_from_exchange(self):
        if self.mode == "backtest": return
        try:
            brl = await self.exchange.get_balance('BRL')
            usdt = await self.exchange.get_balance('USDT')
            if abs(self.balance - brl) > 0.01 or abs(self.usdt_balance - usdt) > 0.01:
                print(f"[SYNC] Saldo Reconciliado: BRL {self.balance:.2f} -> {brl:.2f} | USDT {self.usdt_balance:.2f} -> {usdt:.2f}")
                self.balance = brl; self.usdt_balance = usdt
                self.save_balance(); self.save_state()
            self.last_balance_sync = datetime.now()
        except Exception as e:
            print(f"[SYNC] Erro ao sincronizar saldos: {e}")

    def notify_telegram(self, msg, title="BTC BOT"):
        self.dashboard_logs.appendleft(msg)
        if not self.telegram_token or not self.telegram_chat_id or "seu_token" in self.telegram_token: return
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {"chat_id": self.telegram_chat_id, "text": f"<b>[{title}]</b>\n{msg}", "parse_mode": "HTML"}
            requests.post(url, json=payload, timeout=5)
        except Exception: pass

    def _render_dashboard(self, ts, macro_data, miro_data, asset_signals, yield_info, usdt_data, xaut_data, agent_res):
        header = f"+{'-'*80}+\n| >>> ADVANCED MULTICORE BTC BOT | {ts} | Equity: R$ {self.total_equity:3,.2f} |\n"
        header += f"| Saldo Disponivel: R$ {self.balance:,.2f} | USDT: {self.usdt_balance:.2f} |\n"
        m_mult, m_msg = self.agent.radar.get_recommended_position_mult()
        header += f"| Macro Risk Score: {self.macro_risk:.2f} | Recommendation: {m_msg} |\n+{'-'*80}+\n"
        
        port_lines = []
        for asset, pos_list in self.positions.items():
            for p in pos_list:
                pnl = (asset_signals.get(asset,{}).get('price', p['entry']) / p['entry'] - 1) * p['signal'] if p['entry'] != 0 else 0.0
                port_lines.append(f"| {asset} ({p['signal']}): @ {p['entry']:,.2f} | PnL: {pnl:+.2%} |")
        
        portfolio = f"| [PORTFOLIO] Ativos em Carteira ({len(port_lines)}): |\n+{'-'*80}+\n"
        for pl in port_lines: portfolio += pl + "\n"
        if not port_lines: portfolio += "| Nenhuma posicao aberta no momento. |\n"
        portfolio += f"+{'-'*80}+\n"
        
        yield_s = f"| [COFRE BRL] {yield_info['symbol'] if yield_info else 'Nenhum'}: {yield_info['yield_apr']:.2% if yield_info else 0.0} a.a. |\n+{'-'*80}+\n"
        usdt_s = f"| [USDT/BRL] Preco: {usdt_data['price']:,.2f} | RSI: {usdt_data['rsi']:.1f} | Saldo: {self.usdt_balance:,.2f} USDT |\n+{'-'*80}+\n"
        
        alpha = "| [ALPHA ML ] Sinais baseados em Order Flow & ML: |\n"
        for asset, sig in asset_signals.items():
            alpha += f"| {asset:8} : {sig['signal']:>2} | Prob: {sig['prob']:>5.1%} | {sig['reason']:<30} |\n"
        alpha += f"| [STRATEGIST] Decisao: {agent_res['decision']:8} | Mult: {agent_res['allocation_mult']:.2f} | CAUTION: {str(self.caution_mode):5} |\n+{'-'*80}+\n"
        
        xaut_s = f"| [XAUT/BTC] Ratio: {xaut_data['ratio']:.6f} | RSI: {xaut_data['rsi']:.1f} | Pos: {xaut_data['open_count']}/3 | PnL: {xaut_data['pnl']:+.6f} BTC |\n+{'-'*80}+\n"
        
        logs = "| # LOG RECENTE: |\n"
        for l in self.dashboard_logs: logs += f"| > {l:<76} |\n"
        logs += f"+{'-'*80}+\n"
        
        miro = f"[ORACLE LOCAL] Personas Reportam: {miro_data['sentiment']} ({miro_data['confidence']:.0%}) | Mult: {self.oracle_state.get('multiplier',1.0):.2f}\n"
        print(header + portfolio + yield_s + usdt_s + alpha + xaut_s + logs + miro)

    async def get_real_balance_async(self, a):
        try: return await self.exchange.get_balance(a)
        except Exception: return self.balance

    @property
    def client(self): return getattr(self.exchange, 'client', None)

    async def format_quantity_async(self, asset, qty):
        try:
            info = await self.exchange.get_symbol_info(asset)
            if info:
                for f in info['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        ss = float(f['stepSize'])
                        prec = int(round(-math.log(ss, 10), 0))
                        return math.floor(qty * (10**prec)) / (10**prec)
        except Exception: pass
        return round(qty, 5)

    def _process_usdt(self, macro_risk):
        df = self.engine.fetch_usdt_brl_data(limit=100)
        if df.empty: return {"price": 5.50, "rsi": 50, "balance": self.usdt_balance}
        price = float(df['close'].values[-1])
        sig, conf, reason, metrics = self.usdt_logic.get_signal(df, macro_risk)
        dec, areason = self.agent.assess_usdt_opportunity(sig, conf, reason)
        if dec == "APPROVE":
            if sig == 1 and self.balance >= 100:
                self.balance -= 100; self.usdt_balance += 100 / price
                self.async_log(self.log_file, f"[USDT BUY] 100 BRL @ {price:.2f}"); self.save_balance(); self.save_state()
            elif sig == -1 and self.usdt_balance > 10:
                self.balance += self.usdt_balance * price * 0.999
                self.async_log(self.log_file, f"[USDT SELL] {self.usdt_balance:.2f} USDT @ {price:.2f}")
                self.usdt_balance = 0; self.save_balance(); self.save_state()
        return {"price": price, "rsi": metrics.get('rsi', 50), "balance": self.usdt_balance}

    def _process_xaut(self):
        df = self.engine.fetch_xaut_ratio(limit=100)
        if df.empty: return {"ratio": 0, "rsi": 50, "bb_pct": 0.5, "open_count": 0, "pnl": 0, "reason": "No data", "conf": 0}
        ratio = float(df['close'].values[-1])
        sig, conf, reason, metrics = self.xaut_analyzer.get_signal(df)
        latent_pnl = 0
        with self.xaut_lock:
            rem = []
            for p in self.xaut_positions:
                p_pnl = (ratio / p['ratio_entry'] - 1) if p.get('ratio_entry', 0) != 0 else 0.0
                latent_pnl += (p['xaut_qty'] * ratio) - p['cost_btc']
                if p_pnl > 0.04 or p_pnl < -0.02: self.notify_telegram(f"FECHADO XAUT: {p_pnl:+.2%}", title="XAUT EXIT")
                else: rem.append(p)
            self.xaut_positions = rem
        return {"ratio": ratio, "rsi": metrics.get('rsi', 50), "bb_pct": metrics.get('bb_pct', 0.5), "open_count": len(self.xaut_positions), "pnl": latent_pnl, "reason": reason, "conf": conf}

    async def _train_initial_evo_pop(self):
        loop = asyncio.get_running_loop()
        tasks = []
        for dna in self.evo_engine.population:
            for asset in self.assets:
                brain = self.evo_brains[dna.id][asset]
                df = self.engine.fetch_binance_klines(asset, limit=1000)
                if not df.empty:
                    df = self.engine.apply_indicators(df)
                    tasks.append(loop.run_in_executor(self.executor, brain.train, df))
        if tasks: await asyncio.gather(*tasks)

    async def run_async(self):
        while True:
            try:
                ts = datetime.now().strftime('%H:%M:%S'); self.last_tick = time.time()
                loop = asyncio.get_running_loop()
                try:
                    macro_task = loop.run_in_executor(self.executor, self.engine.fetch_macro_data)
                    btc_dom_task = loop.run_in_executor(self.executor, self.cg_client.get_btc_dominance)
                    macro_data, self.btc_dominance = await asyncio.wait_for(asyncio.gather(macro_task, btc_dom_task), timeout=20.0)
                except Exception: 
                    macro_data = {'dxy_change': 0, 'sp500_change': 0, 'gold_change': 0}
                    if not hasattr(self, 'btc_dominance'): self.btc_dominance = 50.0
                
                miro_data = {"sentiment": self.oracle_state["sentiment"], "confidence": self.oracle_state["confidence"]}
                m_sent = miro_data['sentiment']; news_sent = miro_data['confidence'] if m_sent == "Bullish" else (-miro_data['confidence'] if m_sent == "Bearish" else 0)
                self.macro_risk = self.agent.radar.get_macro_score(macro_data.get('dxy_change',0), macro_data.get('sp500_change',0), macro_data.get('gold_change',0), news_sent)
                self.macro_status = {'is_extreme': self.agent.radar.is_risk_off_extreme(macro_data.get('dxy_change',0), macro_data.get('sp500_change',0))[0]}

                asset_signals = {}; signals_lock = Lock()
                async def scan_asset(asset):
                    try:
                        df = await loop.run_in_executor(self.executor, self.engine.fetch_binance_klines, asset, "1h", 1000)
                        if df.empty: return
                        df = self.engine.apply_indicators(df)
                        imbalance = await loop.run_in_executor(self.executor, self.engine.fetch_order_book_imbalance, asset)
                        
                        tasks = [loop.run_in_executor(self.process_executor, _cpu_heavy_predict, brain, df.copy(), self.macro_risk, self.btc_dominance, 0.45) 
                                 for brain in [self.brains[asset], self.shadow_brains[asset], self.evo_brains[self.evo_engine.population[0].id][asset]]]
                        
                        results = await asyncio.gather(*tasks)
                        (sig, prob, reason, price, rel, atr) = results[0]; (s_sig, s_prob, s_reason, _, _, _) = results[1]
                        
                        t_sigs = {'live': {'sig': sig, 'prob': prob}, 'shadow': {'sig': s_sig, 'prob': s_prob}, 'ancestral': {'sig': results[2][0], 'prob': results[2][1]}}
                        fsig, fconf, treason = self.tribunal.evaluate_signals(t_sigs, {}, failure_risk=0.1, macro_status=self.macro_status)
                        
                        with signals_lock:
                            asset_signals[asset] = {'signal': fsig, 'prob': fconf, 'reason': treason, 'price': price, 'reliability': rel, 'atr': atr, 'imbalance': imbalance}
                    except Exception: pass

                await asyncio.gather(*(scan_asset(a) for a in self.assets))
                agent_res = self.agent.run({'tier2': sum([s['signal'] for s in asset_signals.values()])}, macro_data)
                
                for asset, s in asset_signals.items():
                    active = self.positions.get(asset, [])
                    rem = []
                    for p in active:
                        pnl = (s['price']/p['entry'] - 1) * p['signal'] if p['entry'] != 0 else 0.0
                        act, r_reason = self.risk_manager.check_exit_conditions(asset, p.get('id','0'), s['price'], p['entry'], p['signal'], "HOLD", atr_value=s.get('atr'))
                        if act == 'SELL':
                            if self.shadow_mode or p.get('is_shadow'):
                                self.ledger.close_position(asset); self.notify_telegram(f"[SHADOW] FECHADO {asset}: {pnl:+.2%}")
                            else:
                                order = await self.limit_executor.execute_limit_order(asset, SIDE_SELL if p['signal']==1 else SIDE_BUY, p['qty'])
                                if order:
                                    self.balance += p['cost'] * (1 + pnl - 0.001); self.ledger.close_position(asset); self.save_balance()
                                    self.notify_telegram(f"FECHADO {asset}: {pnl:+.2%}")
                        else: rem.append(p)
                    self.positions[asset] = rem

                    if s['signal'] != 0 and not self.positions[asset]:
                        kelly = self.risk_manager.get_kelly_trade_amount(self.total_equity, s['prob'])
                        sizing = kelly * s['prob'] * (1 - self.risk_manager.calculate_bunker_allocation(self.macro_risk))
                        if sizing >= 10 and self.balance >= sizing:
                            dec, ar, smod = self.agent.assess_trade(asset, s['signal'], s['prob'], s['reason'], reliability=s.get('reliability', 1.0), caution_mode=self.caution_mode, book_imbalance=s.get('imbalance', 0.0))
                            if dec == "APPROVE":
                                qty = await self.format_quantity_async(asset, sizing / s['price'])
                                if self.shadow_mode:
                                    pos_data = {"entry": s['price'], "signal": s['signal'], "qty": qty, "cost": sizing, "time": datetime.now().isoformat(), "is_shadow": True}
                                    self.positions[asset].append(pos_data); self.ledger.save_active_position(asset, pos_data, is_shadow=True)
                                    self.notify_telegram(f"[SHADOW] ABERTO {asset}")
                                else:
                                    order = await self.limit_executor.execute_limit_order(asset, SIDE_BUY if s['signal']==1 else SIDE_SELL, qty)
                                    if order:
                                        self.balance -= sizing; pos_data = {"entry": s['price'], "signal": s['signal'], "qty": qty, "cost": sizing, "time": datetime.now().isoformat(), "is_shadow": False}
                                        self.positions[asset].append(pos_data); self.ledger.save_active_position(asset, pos_data); self.save_balance(); self.save_state()

                usdt_data = self._process_usdt(self.macro_risk); xaut_data = self._process_xaut()
                yield_info = None # Simplified yield fetch
                self.total_equity = self.balance + (usdt_data['price'] * usdt_data['balance'])
                for asset, pos_list in self.positions.items():
                    for p in pos_list:
                        p_price = asset_signals.get(asset, {}).get('price', p['entry'])
                        pnl = (p_price/p['entry'] - 1) * p['signal'] if p['entry'] != 0 else 0.0
                        self.total_equity += p['cost'] * (1 + pnl)
                
                if self.initial_equity is None: self.initial_equity = self.total_equity; self.check_caution_at = datetime.now() + timedelta(minutes=30)
                elif not self.caution_mode and datetime.now() >= self.check_caution_at:
                    if (self.total_equity / self.initial_equity) < 0.995: self.caution_mode = True; self.notify_telegram("MODO CAUTELA ATIVADO")
                
                if datetime.now() - self.last_balance_sync > timedelta(minutes=15): await self.sync_balances_from_exchange()
                self.save_balance(); self.save_state()
                self._render_dashboard(ts, macro_data, miro_data, asset_signals, yield_info, usdt_data, xaut_data, agent_res)
            except Exception as e: print(f"Error: {e}")
            await asyncio.sleep(30)

async def main(bot):
    if hasattr(bot.exchange, 'initialize'): await bot.exchange.initialize()
    if bot.mode != "backtest":
        bot.listen_key = await bot.exchange.start_user_data_stream()
        await bot.sync_balances_from_exchange()
    supervisor = WebSocketSupervisor(bot); asyncio.create_task(supervisor.start())
    asyncio.create_task(bot._train_initial_evo_pop()); asyncio.create_task(bot.oracle.start_loop())
    await bot.run_async()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', type=str, default='backtest')
    args = parser.parse_args()
    try:
        bot = ScoutBot(mode=args.mode)
        asyncio.run(main(bot))
    except Exception as e:
        import traceback, sys
        print(f"[FATAL STARTUP ERROR] {e}"); traceback.print_exc(); sys.exit(1)
