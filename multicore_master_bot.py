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
import math
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from threading import Lock, Thread
from collections import deque
from dotenv import load_dotenv
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET

# Import custom modules
from data.data_engine import DataEngine
from logic.basis_logic import BasisLogic
from logic.ml_brain import MLBrain
from logic.order_flow_logic import OrderFlowLogic
from logic.xaut_logic import XAUTAnalyzer
from logic.market_memory import MarketMemory
from logic.strategist_agent import StrategistAgent
from logic.usdt_brl_logic import UsdtBrlLogic
from logic.local_oracle import LocalOracle
from logic.coingecko_client import CoinGeckoClient
from logic.evolutionary_engine import EvolutionaryEngine, DNA
from logic.tribunal import ConsensusTribunal
from logic.risk_manager import RiskManager
from logic.execution import BinanceLive, BinanceTestnet, BacktestEngine
from logic.execution.limit_executor import LimitExecutor
from logic.database.ledger import Ledger
from logic.watchdog import Watchdog

load_dotenv()
sys.stdout.reconfigure(line_buffering=True)
import logging

def _cpu_heavy_predict(brain, df, macro_risk=0.5, btc_dom=50.0, min_conf=0.45):
    try:
        df['macro_risk'] = macro_risk
        df['btc_dominance'] = btc_dom
        df = brain.prepare_features(df)
        if df.empty: return 0, 0.0, "Dados insuficientes apos limpeza", 0.0, 0.0, 0.0
        
        current_price = float(df['close'].values[-1])
        curr_feat = df[brain.feature_cols].values[-1]
        
        # Extrair ATR se disponivel para o RiskManager
        atr = float(df['feat_atr'].values[-1]) if 'feat_atr' in df.columns else 0.0
        
        signal, prob, reason, reliability = brain.predict_signal(curr_feat, min_confidence=min_conf)
        return signal, prob, reason, current_price, reliability, atr
    except Exception as e:
        return 0, 0.0, f"Erro Predicao: {e}", 0.0, 0.0, 0.0

class WebSocketSupervisor:
    def __init__(self, bot_instance):
        self.bot = bot_instance
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
            return # Retorna para o loop do start() que vai chamar de novo

        try:
            bm = BinanceSocketManager(self.bot.client)
            streams = [f"{s.lower()}@ticker" for s in self.bot.assets]
            if "usdtbrl@ticker" not in streams: streams.append("usdtbrl@ticker")
            
            # Se tivermos uma listen key, adicionamos o stream de usuario
            user_socket = None
            if self.bot.listen_key:
                self.logger.info(f"[SUPERVISOR] Adicionando User Data Stream: {self.bot.listen_key[:10]}...")
                user_socket = bm.user_socket()

            self.logger.info(f"[SUPERVISOR] Iniciando Multiplex Socket para {len(streams)} streams...")
            
            # Precisamos lidar com multiplos sockets se o user_socket existir
            if user_socket:
                async with bm.multiplex_socket(streams) as ms, user_socket as us:
                    while True:
                        # Monitoramos ambos os sockets
                        done, pending = await asyncio.wait(
                            [ms.recv(), us.recv()],
                            return_when=asyncio.FIRST_COMPLETED,
                            timeout=30
                        )
                        for task in done:
                            res = task.result()
                            if res and 'data' in res: # Market Data
                                data = res['data']; symbol = data['s']
                                self.bot.live_prices[symbol] = float(data['c'])
                            elif res and 'e' in res: # User Data Event
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
            raise # Deixa o start() lidar com o backoff

    async def _handle_user_event(self, event):
        """Lida com eventos de balance e ordens vindos do WebSocket da Binance."""
        etype = event.get('e')
        if etype == 'outboundAccountPosition':
            self.logger.info("[SUPERVISOR] Atualizacao de Saldo via WebSocket detectada.")
            for balance in event.get('B', []):
                asset = balance.get('a')
                free = float(balance.get('f'))
                if asset == 'BRL':
                    self.bot.balance = free
                elif asset == 'USDT':
                    self.bot.usdt_balance = free
            self.bot.save_balance()
            self.bot.save_state()
        elif etype == 'balanceUpdate':
            self.logger.info(f"[SUPERVISOR] Balance Update: {event.get('a')} {event.get('d')}")
            # Forca um sync completo na proxima iteracao
            self.bot.last_balance_sync = datetime.now() - timedelta(hours=1)


    async def _handle_reconnection(self):
        for s in self.bot.assets: self.bot.live_prices[s] = 0.0
        self.bot.live_prices["USDTBRL"] = 0.0
        wait_time = min(self._backoff_delay, 60)
        await asyncio.sleep(wait_time)
        self._backoff_delay *= 2

    def stop(self): self._is_running = False

def orjson_default(obj):
    if isinstance(obj, (np.integer, np.floating)): return obj.item()
    if isinstance(obj, np.ndarray): return obj.tolist()
    raise TypeError

class MulticoreMasterBot:
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

        self.trade_amount = 100.0
        self.fee_rate = 0.001
        self.take_profit = 0.03
        self.stop_loss = 0.015
        self.min_binance_amount = 10.0
        self.balance_file = "results/balance_state.txt"
        
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
        self.ledger = Ledger()
        self.limit_executor = LimitExecutor(self.exchange)
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.use_mirofish = False # MiroFish desativado permanentemente em favor do LocalOracle
        self.listen_key = None
        self.last_balance_sync = datetime.now()
        
        # Health & Monitoring
        self.last_tick = time.time()
        self.watchdog = Watchdog(self)
        self.watchdog.start()
        
        self.caution_mode = False
        self.initial_equity = None # Sera setado no primeiro ciclo
        self.check_caution_at = None

        self.log_queue = queue.Queue()
        self.log_thread = Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()
        self.pos_lock = Lock()
        self.live_prices = {}
        self.executor = ThreadPoolExecutor(max_workers=6)
        self.process_executor = ProcessPoolExecutor(max_workers=6)

        self.liquidity_mult = {"BTCBRL":1.0, "ETHBRL":0.95, "SOLBRL":0.85, "LINKBRL":0.8, "AVAXBRL":0.8, "RENDERBRL":0.75}
        # Sincronizacao de persistencia: Prioridade para o Ledger (SQLite)
        saved_balance = self.ledger.get_last_balance()
        self.balance = saved_balance if saved_balance is not None else self.load_balance()
        self.positions = self.ledger.load_active_positions()
        if not self.positions: self.positions = self.load_state()
        
        self.total_equity = self.balance
        self.dashboard_logs = deque(maxlen=5)
        self.last_status_report = datetime.now() - timedelta(hours=3, minutes=55) # Primeiro report em 5 min
        
        print("[INIT] Booting Multicore Brains...")
        os.makedirs("models", exist_ok=True)
        for asset in assets:
            model_path = f"models/{asset.lower()}_brain_v1.pkl"
            if self.brains[asset].load_model(model_path):
                print(f"[BOOT] {asset}: Modelo LIVE recuperado.")
            else:
                print(f"[WARN] {asset}: Treinando do zero...")
                df = self.engine.fetch_binance_klines(asset, limit=1000)
                if not df.empty:
                    df = self.engine.apply_indicators(df)
                    score = self.brains[asset].train(df, train_full=True, tp=self.take_profit, sl=self.stop_loss)
                    self.brains[asset].save_model(model_path)
                    self.stats[asset]["oos_score"] = score

        # Background tasks moved to main() to avoid "no running event loop" error

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
                    with open(path, "wb") as f: f.write(json.dumps(content, option=json.OPT_INDENT_2))
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
                with open(self.status_file, "rb") as f:
                    s = json.loads(f.read())
                    self.usdt_balance = s.get("usdt_balance", 0.0)
                    self.xaut_positions = s.get("xaut_positions", [])
                    self.caution_mode = s.get("caution_mode", False)
                    return s.get("positions", {})
            except Exception: pass
        self.usdt_balance = 0.0
        return {}

    def save_state(self):
        with self.pos_lock:
            # Stats de confiabilidade dos cerebros
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
        """Sincronizacao forçada via REST API para evitar deriva de saldo."""
        if self.mode == "backtest": return
        try:
            brl = await self.exchange.get_balance('BRL')
            usdt = await self.exchange.get_balance('USDT')
            
            # Log apenas se houver mudanca significativa (> 0.01)
            if abs(self.balance - brl) > 0.01 or abs(self.usdt_balance - usdt) > 0.01:
                print(f"[SYNC] Saldo Reconciliado: BRL {self.balance:.2f} -> {brl:.2f} | USDT {self.usdt_balance:.2f} -> {usdt:.2f}")
                self.balance = brl
                self.usdt_balance = usdt
                self.save_balance()
                self.save_state()
            self.last_balance_sync = datetime.now()
        except Exception as e:
            print(f"[SYNC] Erro ao sincronizar saldos: {e}")

    def notify_telegram(self, msg, title="BTC BOT"):
        # Log para o dashboard
        self.dashboard_logs.appendleft(msg)
        if not self.telegram_token or not self.telegram_chat_id or "seu_token" in self.telegram_token:
            return

        try:
            full_msg = f"<b>[{title}]</b>\n{msg}"
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": full_msg,
                "parse_mode": "HTML"
            }
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"[TELEGRAM] Erro ao enviar: {e}")

    def _render_dashboard(self, ts, macro_data, miro_data, asset_signals, yield_info, usdt_data, xaut_data, agent_res):
        """Builds the stylized console UI as requested by the user."""
        header = f"+{'-'*80}+\n"
        header += f"| >>> ADVANCED MULTICORE BTC BOT | {ts} | Equity: R$ {self.total_equity:,.2f} |\n"
        header += f"| Saldo Disponivel: R$ {self.balance:,.2f} | USDT: {self.usdt_balance:.2f} |\n"
        
        m_mult, m_msg = self.agent.radar.get_recommended_position_mult()
        header += f"| Macro Risk Score: {self.macro_risk:.2f} | Recommendation: {m_msg} |\n"
        header += f"+{'-'*80}+\n"
        
        # Portfolio
        port_lines = []
        for asset, pos_list in self.positions.items():
            for p in pos_list:
                pnl = (asset_signals.get(asset,{}).get('price', p['entry']) / p['entry'] - 1) * p['signal']
                port_lines.append(f"| {asset} ({p['signal']}): @ {p['entry']:,.2f} | PnL: {pnl:+.2%} |")
        
        portfolio = f"| [PORTFOLIO] Ativos em Carteira ({len(port_lines)}): |\n"
        portfolio += f"+{'-'*80}+\n"
        for pl in port_lines: portfolio += pl + "\n"
        if not port_lines: portfolio += "| Nenhuma posicao aberta no momento. |\n"
        portfolio += f"+{'-'*80}+\n"
        
        # Yields
        yield_s = ""
        if yield_info:
            yield_s = f"| [COFRE BRL] Melhor Yield BTC Futuros: {yield_info['yield_apr']:.2%} a.a. |\n"
        else:
            yield_s = "| [COFRE BRL] Buscando contratos de entrega... |\n"
        yield_s += f"+{'-'*72}+\n"
        
        # USDT
        usdt_s = f"| [USDT/BRL] Preco: {usdt_data['price']:,.2f} | RSI: {usdt_data['rsi']:.1f} | Saldo: {self.usdt_balance:,.2f} USDT |\n"
        usdt_s += f"+{'-'*72}+\n"
        
        # Alpha Signals
        alpha = f"| [ALPHA ML ] Sinais baseados em Order Flow & ML: |\n"
        for asset, sig in asset_signals.items():
            label = "Neutro"
            if sig['signal'] == 1: label = "COMPRA"
            elif sig['signal'] == -1: label = "VENDA"
            
            conv_label = "Conviccao Baixa"
            if sig['prob'] > 0.70: conv_label = "Confluencia ML"
            if sig['prob'] > 0.85: conv_label = "ALTA CONVICCAO"
            
            alpha += f"| {asset:8} : {sig['signal']:>2} | Prob: {sig['prob']:>5.1%} | {conv_label} ({sig['prob']:.1%}) | {sig['reason']:<20} |\n"
        
        alpha += f"| [STRATEGIST] Decisao: {agent_res['decision']:8} | Mult: {agent_res['allocation_mult']:.2f} | CAUTION: {str(self.caution_mode):5} |\n"
        alpha += f"+{'-'*80}+\n"
        
        # XAUT
        xaut_s = f"| [XAUT/BTC] Ratio: {xaut_data['ratio']:.6f} BTC/XAUT | RSI ratio: {xaut_data['rsi']:.1f} | BB%: {xaut_data['bb_pct']:.2f} |\n"
        xaut_s += f"| Pool BTC: {xaut_data['pool']:.5f} BTC livre | Posicoes: {xaut_data['open_count']}/3 | PnL latente: {xaut_data['pnl']:+.6f} BTC |\n"
        xaut_s += f"| . Sinal: {xaut_data['reason']:20} | Conf: {xaut_data['conf']:>3.0%} | Thresh: 55% |\n"
        xaut_s += f"+{'-'*72}+\n"
        
        # Logs
        logs = f"| # LOG RECENTE: |\n"
        for l in self.dashboard_logs:
            logs += f"| > {l:<70} |\n"
        if not self.dashboard_logs: logs += "| > Nenhum log recente. |\n"
        logs += f"+{'-'*72}+\n"
        
        # Oracle Local
        miro_sent = miro_data.get('sentiment', 'Neutral')
        miro_conf = miro_data.get('confidence', 0.5)
        miro_score = miro_conf if miro_sent == "Bullish" else (-miro_conf if miro_sent == "Bearish" else 0)
        
        status_oraculo = "ATIVADO (LocalOracle)"
        miro = f"[ORACLE LOCAL] Personas Reportam: {miro_sent} ({miro_conf:.0%}) | Mult: {self.oracle_state.get('multiplier',1.0):.2f} [{status_oraculo}]\n"
        
        # Composite
        full = header + portfolio + yield_s + usdt_s + alpha + xaut_s + logs + miro
        try:
            print(full)
        except UnicodeEncodeError:
            print(full.encode('ascii', 'ignore').decode('ascii'))

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
        if df.empty: 
            # Fallback to a safe approximate price if no data available to avoid 0 equity
            return {"price": 5.50, "rsi": 50, "balance": self.usdt_balance}
        price = float(df['close'].values[-1])
        sig, conf, reason, metrics = self.usdt_logic.get_signal(df, macro_risk)
        dec, areason = self.agent.assess_usdt_opportunity(sig, conf, reason)
        if dec == "APPROVE":
            if sig == 1 and self.balance >= 100:
                self.balance -= 100
                self.usdt_balance += 100 / price
                self.async_log(self.log_file, f"[USDT BUY] BRL 100 -> {100/price:.2f} USDT @ {price:.2f}")
                self.save_balance(); self.save_state()
            elif sig == -1 and self.usdt_balance > 10:
                old_usdt = self.usdt_balance
                self.balance += self.usdt_balance * price * 0.999
                self.usdt_balance = 0
                self.async_log(self.log_file, f"[USDT SELL] {old_usdt:.2f} USDT -> BRL @ {price:.2f}")
                self.save_balance(); self.save_state()
        return {"price": price, "rsi": metrics.get('rsi', 50), "balance": self.usdt_balance}

    def _process_xaut(self):
        df = self.engine.fetch_xaut_ratio(limit=100)
        if df.empty: return {"ratio": 0, "rsi": 50, "bb_pct": 0.5, "pool": 0, "open_count": 0, "pnl": 0, "reason": "No data", "conf": 0}
        ratio = float(df['close'].values[-1])
        sig, conf, reason, metrics = self.xaut_analyzer.get_signal(df)
        
        # PnL Latente
        latent_pnl = 0
        with self.xaut_lock:
            rem = []
            for p in self.xaut_positions:
                p_pnl = (ratio / p['ratio_entry'] - 1)
                latent_pnl += (p['xaut_qty'] * ratio) - p['cost_btc']
                if p_pnl > 0.04 or p_pnl < -0.02: 
                    self.notify_telegram(f"FECHADO XAUT: {p_pnl:+.2%}", title="XAUT EXIT")
                else: rem.append(p)
            self.xaut_positions = rem
        
        return {
            "ratio": ratio, 
            "rsi": metrics.get('rsi', 50), 
            "bb_pct": metrics.get('bb_pct', 0.5),
            "pool": 0.0, # Placeholder for BTC pool
            "open_count": len(self.xaut_positions),
            "pnl": latent_pnl,
            "reason": reason,
            "conf": conf
        }

    def _calculate_regime_metrics(self, df):
        if len(df) < 24: return {"vol": 0, "trend": 0}
        v = float(df['close'].pct_change().std())
        t = (df['close'].iloc[-1] / df['close'].iloc[-24]) - 1
        return {"vol": v, "trend": t}

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

    def _dissect_trade_failure(self, s, label):
        try: self.memory.record_failed_state(metrics=s.get('metrics',{}), cause=label)
        except Exception: pass

    async def run_async(self):
        iter_count = 0
        while True:
            try:
                ts = datetime.now().strftime('%H:%M:%S')
                self.last_tick = time.time()
                loop = asyncio.get_running_loop()
                # Fetch Macro, Sentiment and BTC Dominance with Timeouts
                try:
                    self.oracle_state["macro_risk"] = self.macro_risk
                    macro_task = loop.run_in_executor(self.executor, self.engine.fetch_macro_data)
                    btc_dom_task = loop.run_in_executor(self.executor, self.cg_client.get_btc_dominance)
                    
                    macro_data, self.btc_dominance = await asyncio.wait_for(
                        asyncio.gather(macro_task, btc_dom_task),
                        timeout=20.0
                    )
                    miro_data = {"sentiment": self.oracle_state["sentiment"], "confidence": self.oracle_state["confidence"]}
                except asyncio.TimeoutError:
                    print("[WARN] Timeout buscando dados externos. Usando fallbacks...")
                    macro_data = {'dxy_change': 0, 'sp500_change': 0, 'gold_change': 0}
                    miro_data = {"sentiment": self.oracle_state["sentiment"], "confidence": self.oracle_state["confidence"]}
                    # self.btc_dominance mantém valor anterior
                except Exception as e:
                    print(f"[ERROR] Erro em dados externos: {e}")
                    macro_data = {'dxy_change': 0, 'sp500_change': 0, 'gold_change': 0}
                    miro_data = {"sentiment": self.oracle_state["sentiment"], "confidence": self.oracle_state["confidence"]}
                
                m_sent = miro_data['sentiment']; m_conf = miro_data['confidence']
                news_sent = m_conf if m_sent == "Bullish" else (-m_conf if m_sent == "Bearish" else 0)
                
                # Radar Macro
                self.macro_risk = self.agent.radar.get_macro_score(macro_data.get('dxy_change',0), macro_data.get('sp500_change',0), macro_data.get('gold_change',0), news_sent)
                is_extreme, m_reason = self.agent.radar.is_risk_off_extreme(macro_data.get('dxy_change',0), macro_data.get('sp500_change',0))
                self.macro_status = {'is_extreme': is_extreme, 'reason': m_reason}

                # Periodic Risk Calibration (Every hour)
                if datetime.now().minute == 0 and datetime.now().second < 30:
                    perf = self.ledger.get_recent_performance(limit=20)
                    if perf['count'] >= 5:
                        # Puxamos a media de 'oos_score' dos cerebros como acuracia esperada
                        avg_expected = sum([v['oos_score'] for v in self.stats.values()]) / len(self.assets) if self.assets else 0.65
                        self.risk_manager.calibrate_ego_buffer(perf['accuracy'], expected_acc=max(0.5, avg_expected))

                asset_signals = {}; signals_lock = Lock()
                async def scan_asset(asset):
                    try:
                        df = await loop.run_in_executor(self.executor, self.engine.fetch_binance_klines, asset, "1h", 1000)
                        if df.empty: return
                        df = self.engine.apply_indicators(df)
                        
                        # Brains candidates
                        live_brain = self.brains[asset]
                        shadow_brain = self.shadow_brains[asset]
                        
                        # Identify Alfa for Ancestral vote
                        alfa_dna = self.evo_engine.population[0]
                        ancestral_brain = self.evo_brains[alfa_dna.id][asset]
                        
                        # Parallelize predictions across ProcessPoolExecutor
                        tasks = [
                            loop.run_in_executor(self.process_executor, _cpu_heavy_predict, live_brain, df.copy(), self.macro_risk, self.btc_dominance, 0.45),
                            loop.run_in_executor(self.process_executor, _cpu_heavy_predict, shadow_brain, df.copy(), self.macro_risk, self.btc_dominance, 0.45),
                            loop.run_in_executor(self.process_executor, _cpu_heavy_predict, ancestral_brain, df.copy(), self.macro_risk, self.btc_dominance, 0.45)
                        ]
                        
                        results = await asyncio.gather(*tasks)
                        (sig, prob, reason, price, rel, atr) = results[0]
                        (s_sig, s_prob, _, _, _, _) = results[1]
                        (a_sig, a_prob, _, _, _, _) = results[2]
                        
                        f_risk = self.memory.check_failure_risk(0.01, 0, news_sent)
                        t_sigs = {
                            'live': {'sig': sig, 'prob': prob},
                            'shadow': {'sig': s_sig, 'prob': s_prob},
                            'ancestral': {'sig': a_sig, 'prob': a_prob}
                        }
                        fsig, fconf, treason = self.tribunal.evaluate_signals(t_sigs, {}, failure_risk=f_risk, macro_status=self.macro_status)
                        
                        acc = self.stats.get('global_acc_4h', 0.5)
                        conv = (fconf * acc) * self.liquidity_mult.get(asset, 0.5)
                        
                        with signals_lock:
                            asset_signals[asset] = {
                                'signal': fsig, 
                                'prob': fconf, 
                                'conviction': conv, 
                                'reason': treason, 
                                'price': price,
                                'reliability': rel,
                                'atr': atr
                            }
                            if fsig != 0: self.signal_history[asset].append({'ts':datetime.now(), 'sig':fsig, 'price':price, 'metrics':{}})
                    except Exception: pass

                await asyncio.gather(*(scan_asset(a) for a in self.assets))
                
                # Agent Decision
                tier2 = sum([s['signal'] for s in asset_signals.values()])
                agent_macro = macro_data.copy()
                agent_macro['news_sentiment'] = news_sent
                agent_res = self.agent.run({'tier2': tier2}, agent_macro)
                final_mult = agent_res['allocation_mult']
                
                # Loop de Execucao
                for asset, s in asset_signals.items():
                    active = self.positions.get(asset, [])
                    if not isinstance(active, list): active = [active] if active else []
                    
                    rem = []
                    for p in active:
                        pnl = (s['price']/p['entry'] - 1) * p['signal']
                        exit_r = None
                        if s['signal'] == -p['signal'] and s['prob'] >= 0.75: exit_r = "REVERSAL"
                        if is_extreme and asset != "BTCBRL": exit_r = "BUNKER_EXIT"
                        
                        act, r_reason = self.risk_manager.check_exit_conditions(asset, p.get('id','0'), s['price'], p['entry'], p['signal'], "HOLD", atr_value=s.get('atr'))
                        if exit_r or act == 'SELL':
                            # Execucao Real/Mock via LimitExecutor
                            qty = p['qty']
                            side = SIDE_SELL if p['signal'] == 1 else SIDE_BUY
                            logger.info(f"[EXEC] Saindo de {asset} via Limit Order...")
                            
                            # Em modo backtest ou testnet/live
                            order = await self.limit_executor.execute_limit_order(asset, side, qty)
                            if order:
                                # Se preenchido, remove da lista
                                final_price = float(order.get('price', s['price']))
                                pnl_real = (final_price/p['entry'] - 1) * p['signal']
                                self.balance += p['cost'] * (1 + pnl_real - 0.001) # Taxa maker menor
                                self.notify_telegram(f"FECHADO {asset}: {exit_r or r_reason} ({pnl_real:+.2%}) @ {final_price}")
                                
                                # Persistencia em Banco de Dados
                                self.ledger.update_position(asset, None) # Remove posicao
                                self.ledger.record_completed_trade(asset, side, p['entry'], final_price, qty, pnl_real, p['cost']*pnl_real, p['time'], exit_r or r_reason)
                                self.memory.record_trade(asset, side, qty, final_price)
                                self.memory.record_outcome(pnl_real)
                                self.save_balance()
                            else:
                                # Fallback para Market se falhar muito
                                logger.warning(f"[EXEC] Falha no Limit Exit para {asset}. Tentando Market...")
                                order = await self.limit_executor.execute_smart_market(asset, side, qty)
                                if order:
                                    rem.append(p) # Remove na proxima iteracao se der erro? Nao, removemos agora
                                    self.notify_telegram(f"FECHADO {asset} (MARKET FALLBACK)")
                        else: rem.append(p)
                    self.positions[asset] = rem

                    # Entries
                    if s['signal'] != 0 and len(self.positions[asset]) < 1:
                        h_pct = self.risk_manager.calculate_bunker_allocation(self.macro_risk)
                        avail = 0.1 if (is_extreme and asset=="BTCBRL") else (0.0 if is_extreme else (1.0 - h_pct))
                        # Use internal model probability (s['prob']) for Kelly instead of hardcoded 0.5
                        kelly = self.risk_manager.get_kelly_trade_amount(self.total_equity, s['prob'])
                        sizing = kelly * s['conviction'] * avail
                        
                        if sizing >= 10 and self.balance >= sizing:
                            # Injected reliability and caution logic
                            dec, ar, smod = self.agent.assess_trade(asset, s['signal'], s['prob'], s['reason'], reliability=s.get('reliability', 1.0), caution_mode=self.caution_mode)
                            if dec == "APPROVE":
                                side = SIDE_BUY if s['signal'] == 1 else SIDE_SELL
                                qty = await self.format_quantity_async(asset, sizing / s['price'])
                                
                                logger.info(f"[EXEC] Entrando em {asset} via Limit Order...")
                                order = await self.limit_executor.execute_limit_order(asset, side, qty)
                                
                                if order:
                                    actual_price = float(order.get('price', s['price']))
                                    actual_sizing = qty * actual_price
                                    self.balance -= actual_sizing
                                    pos_data = {
                                        "entry": actual_price, 
                                        "signal": s['signal'], 
                                        "qty": qty, 
                                        "cost": actual_sizing, 
                                        "time": ts,
                                        "order_id": order.get('orderId')
                                    }
                                    self.positions[asset].append(pos_data)
                                    
                                    # Persistencia em Banco de Dados
                                    self.ledger.update_position(asset, pos_data)
                                    self.memory.record_trade(asset, side, qty, actual_price)
                                    
                                    self.notify_telegram(f"ABERTO {asset}: {side} {qty} @ {actual_price}")
                                    self.save_balance(); self.save_state()
                                else:
                                    logger.warning(f"[EXEC] Falha ao abrir {asset} via Limit Order.")
                            else:
                                print(f"[STRATEGIST] Rejeitado {asset}: {ar}")
                        else:
                            if sizing < 10 and sizing > 0:
                                print(f"[RISK] {asset}: Sizing insuficiente (R$ {sizing:.2f} < 10.00)")
                            elif self.balance < sizing:
                                print(f"[RISK] {asset}: Saldo insuficiente (R$ {self.balance:.2f} < {sizing:.2f})")
                            elif avail == 0:
                                print(f"[RISK] {asset}: Bloqueado pelo modo Bunker (Extreme Risk)")

                # Post-Loop Analysis
                usdt_data = self._process_usdt(self.macro_risk)
                xaut_data = self._process_xaut()
                
                # Fetch Best Yield
                yield_info = None
                try:
                    contracts = self.engine.fetch_delivery_contracts("BTC")
                    if contracts:
                        best_c = None
                        best_apr = -1
                        for c in contracts:
                            b_data = self.engine.fetch_basis_data("BTCUSDT", c['symbol'])
                            if b_data:
                                expiry = self.basis_logic.parse_expiry(c['symbol'])
                                apr = self.basis_logic.calculate_annualized_yield(b_data['spot'], b_data['future'], expiry)
                                if apr > best_apr:
                                    best_apr = apr
                                    best_c = {'symbol': c['symbol'], 'yield_apr': apr}
                        yield_info = best_c
                except Exception: pass

                # Calculate Total Equity
                self.total_equity = self.balance + (usdt_data['price'] * usdt_data['balance'])
                for asset, pos_list in self.positions.items():
                    for p in pos_list:
                        p_price = asset_signals.get(asset, {}).get('price', p['entry'])
                        p_pnl = (p_price / p['entry'] - 1) * p['signal']
                        self.total_equity += p['cost'] * (1 + p_pnl)
                
                # Add XAUT value to equity (converting BTC to BRL)
                # Fallback to a high-last-resort price if BTCBRL fetch fails, or use opening entry if available
                btc_price = asset_signals.get("BTCBRL", {}).get("price", 0.0)
                if btc_price == 0.0 and "BTCBRL" in self.live_prices:
                    btc_price = self.live_prices["BTCBRL"]
                
                    eff_btc_price = btc_price if btc_price > 0 else (p.get('btc_entry_price', 350000.0))
                    self.total_equity += p['cost_btc'] * eff_btc_price * (xaut_data['ratio'] / p['ratio_entry'] if 'ratio_entry' in p else 1.0)

                # Check for Caution Mode (First 30 minutes)
                if self.initial_equity is None:
                    self.initial_equity = self.total_equity
                    self.check_caution_at = datetime.now() + timedelta(minutes=30)
                elif not self.caution_mode and datetime.now() >= self.check_caution_at:
                    if (self.total_equity / self.initial_equity) < 0.995:
                        self.caution_mode = True
                        self.notify_telegram(f"⚠ MODO CAUTELA ATIVADO: Perda de {1 - (self.total_equity/self.initial_equity):.2%} detectada no warmup.")
                        self.save_state()

                # Periodic Balance Reconciliation (Every 15 minutes)
                if datetime.now() - self.last_balance_sync > timedelta(minutes=15):
                    await self.sync_balances_from_exchange()
                    # Renova Listen Key se necessario (a cada 30 min)
                    if self.listen_key and hasattr(self.exchange, 'keep_user_data_stream_alive'):
                        await self.exchange.keep_user_data_stream_alive(self.listen_key)

                self.save_balance(); self.save_state()
                self._render_dashboard(ts, macro_data, miro_data, asset_signals, yield_info, usdt_data, xaut_data, agent_res)
                
                # Relatorio Periodico (Heartbeat) - Cada 4 horas
                if datetime.now() - self.last_status_report > timedelta(hours=4):
                    pos_count = sum(len(p) if isinstance(p, list) else 1 for p in self.positions.values() if p)
                    status_msg = f"🛡️ <b>STATUS:</b> Equity R$ {self.total_equity:,.2f} | Saldo R$ {self.balance:,.2f} | Pos: {pos_count} | 🕒 {ts} | ✅ Normal"
                    self.notify_telegram(status_msg, title="STATUS")
                    self.last_status_report = datetime.now()

            except Exception as e: print(f"Error: {e}")
            await asyncio.sleep(30)

async def main(bot):
    if hasattr(bot.exchange, 'initialize'):
        await bot.exchange.initialize()
    
    # Inicializa Listen Key para User Data Stream (se nao for backtest)
    if bot.mode != "backtest":
        bot.listen_key = await bot.exchange.start_user_data_stream()
        await bot.sync_balances_from_exchange() # Primeiro sync real

    supervisor = WebSocketSupervisor(bot)
    asyncio.create_task(supervisor.start())
    asyncio.create_task(bot._train_initial_evo_pop())
    asyncio.create_task(bot.oracle.start_loop())
    await bot.run_async()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', type=str, default='backtest')
    args = parser.parse_args()
    bot = MulticoreMasterBot(mode=args.mode)
    asyncio.run(main(bot))
