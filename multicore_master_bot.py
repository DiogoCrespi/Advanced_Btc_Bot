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
from logic.mirofish_client import MiroFishClient
from logic.coingecko_client import CoinGeckoClient
from logic.evolutionary_engine import EvolutionaryEngine, DNA
from logic.tribunal import ConsensusTribunal
from logic.risk_manager import RiskManager
from logic.execution import BinanceLive, BinanceTestnet, BacktestEngine

load_dotenv()
sys.stdout.reconfigure(line_buffering=True)
import logging

def _cpu_heavy_predict(brain, df):
    try:
        curr_feat = df[[c for c in df.columns if c.startswith('feat_')]].values[-1]
        current_price = float(df['close'].values[-1])
        signal, prob, reason = brain.predict_signal(curr_feat)
        return signal, prob, reason, current_price
    except Exception as e:
        return 0, 0.0, f"Erro Predicao: {e}", 0.0

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
            
            self.logger.info(f"[SUPERVISOR] Iniciando Multiplex Socket para {len(streams)} streams...")
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
        self.miro_client = MiroFishClient()
        self.miro_sim_id = "live_bot_sim"
        self.memory = MarketMemory()
        self.cg_client = CoinGeckoClient()
        self.stats = {asset: {"oos_score": 0.0} for asset in assets}
        self.risk_manager = RiskManager()
        self.ntfy_url = "http://ntfy"
        self.ntfy_topic = os.getenv("NTFY_TOPIC", "btc_bot_trades")

        self.log_queue = queue.Queue()
        self.log_thread = Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()
        self.pos_lock = Lock()
        self.live_prices = {}
        self.executor = ThreadPoolExecutor(max_workers=6)
        self.process_executor = ProcessPoolExecutor(max_workers=6)

        self.liquidity_mult = {"BTCBRL":1.0, "ETHBRL":0.9, "SOLBRL":0.8, "LINKBRL":0.65, "AVAXBRL":0.65, "RENDERBRL":0.6}
        self.balance = self.load_balance()
        self.positions = self.load_state()
        self.total_equity = self.balance
        self.dashboard_logs = deque(maxlen=5)
        
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
    def save_balance(self): self.log_queue.put(("write", (self.balance_file, f"{self.balance:.2f}")))
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
                    return s.get("positions", {})
            except Exception: pass
        self.usdt_balance = 0.0
        return {}

    def save_state(self):
        with self.pos_lock:
            st = {"balance": self.balance, "usdt_balance": self.usdt_balance, "positions": self.positions, "xaut_positions": self.xaut_positions}
        self.log_queue.put(("save_state", (self.status_file, st)))

    def notify_ntfy(self, msg, title="BTC BOT"):
        # Log para o dashboard
        self.dashboard_logs.appendleft(msg)
        try:
            requests.post(f"{self.ntfy_url}/{self.ntfy_topic}", data=msg.encode('utf-8'), headers={"Title": title}, timeout=5)
        except Exception: pass

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
            
            alpha += f"| {asset:8} : {sig['signal']:>2} | Prob: {sig['prob']:>5.1%} | {conv_label} ({sig['prob']:.1%}) |\n"
        
        alpha += f"| [STRATEGIST] Decisao: {agent_res['decision']:8} | Mult: {agent_res['allocation_mult']:.2f} |\n"
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
        
        # MiroFish
        miro_sent = miro_data.get('sentiment', 'Neutral')
        miro_conf = miro_data.get('confidence', 0.5)
        miro_score = miro_conf if miro_sent == "Bullish" else (-miro_conf if miro_sent == "Bearish" else 0)
        
        miro = f"[MIROFISH] Analise de Sentimento Profundo: {miro_sent} ({miro_conf:.0%}) | Score: {miro_score:.2f}\n"
        
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
                self.save_balance(); self.save_state()
            elif sig == -1 and self.usdt_balance > 10:
                self.balance += self.usdt_balance * price * 0.999
                self.usdt_balance = 0
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
                    self.notify_ntfy(f"FECHADO XAUT: {p_pnl:+.2%}", title="XAUT EXIT")
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
                loop = asyncio.get_running_loop()
                macro_task = loop.run_in_executor(self.executor, self.engine.fetch_macro_data)
                miro_task = loop.run_in_executor(self.executor, self.miro_client.get_sentiment_summary, self.miro_sim_id)
                btc_dom_task = loop.run_in_executor(self.executor, self.cg_client.get_btc_dominance)
                macro_data, miro_data, self.btc_dominance = await asyncio.gather(macro_task, miro_task, btc_dom_task)
                
                m_sent = miro_data['sentiment']; m_conf = miro_data['confidence']
                news_sent = m_conf if m_sent == "Bullish" else (-m_conf if m_sent == "Bearish" else 0)
                
                # Radar Macro
                self.macro_risk = self.agent.radar.get_macro_score(macro_data.get('dxy_change',0), macro_data.get('sp500_change',0), macro_data.get('gold_change',0), news_sent)
                is_extreme, m_reason = self.agent.radar.is_risk_off_extreme(macro_data.get('dxy_change',0), macro_data.get('sp500_change',0))
                self.macro_status = {'is_extreme': is_extreme, 'reason': m_reason}

                asset_signals = {}; signals_lock = Lock()
                async def scan_asset(asset):
                    try:
                        df = await loop.run_in_executor(self.executor, self.engine.fetch_binance_klines, asset, "1h", 1000)
                        if df.empty: return
                        df = self.engine.apply_indicators(df)
                        brain = self.brains[asset]
                        sig, prob, reason, price = await loop.run_in_executor(self.process_executor, _cpu_heavy_predict, brain, df)
                        
                        f_risk = self.memory.check_failure_risk(0.01, 0, news_sent)
                        t_sigs = {'live':{'sig':sig,'prob':prob}, 'shadow':{'sig':0,'prob':0.5}, 'ancestral':{'sig':0,'prob':0.5}}
                        fsig, fconf, treason = self.tribunal.evaluate_signals(t_sigs, {}, failure_risk=f_risk, macro_status=self.macro_status)
                        
                        acc = self.stats.get('global_acc_4h', 0.5)
                        conv = (fconf * acc) * self.liquidity_mult.get(asset, 0.5)
                        
                        with signals_lock:
                            asset_signals[asset] = {'signal': fsig, 'prob': fconf, 'conviction': conv, 'reason': treason, 'price': price}
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
                        
                        act, r_reason = self.risk_manager.check_exit_conditions(asset, p.get('id','0'), s['price'], p['entry'], p['signal'], "HOLD")
                        if exit_r or act == 'SELL':
                            self.balance += p['cost'] * (1 + pnl - 0.002)
                            self.notify_ntfy(f"FECHADO {asset}: {exit_r or r_reason} ({pnl:+.2%})")
                        else: rem.append(p)
                    self.positions[asset] = rem

                    # Entries
                    if s['signal'] != 0 and len(self.positions[asset]) < 1:
                        h_pct = self.risk_manager.calculate_bunker_allocation(self.macro_risk)
                        avail = 0.1 if (is_extreme and asset=="BTCBRL") else (0.0 if is_extreme else (1.0 - h_pct))
                        kelly = self.risk_manager.get_kelly_trade_amount(self.total_equity, 0.5)
                        sizing = kelly * s['conviction'] * avail
                        
                        if sizing >= 10 and self.balance >= sizing:
                            dec, ar, smod = self.agent.assess_trade(asset, s['signal'], s['prob'], s['reason'])
                            if dec == "APPROVE":
                                self.balance -= sizing
                                self.positions[asset].append({"entry": s['price'], "signal": s['signal'], "qty": sizing/s['price'], "cost": sizing, "time": ts})
                                self.notify_ntfy(f"ABERTO {asset}: R$ {sizing:.2f}")

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
                
                for p in self.xaut_positions:
                    eff_btc_price = btc_price if btc_price > 0 else (p.get('btc_entry_price', 350000.0))
                    self.total_equity += p['cost_btc'] * eff_btc_price * (xaut_data['ratio'] / p['ratio_entry'] if 'ratio_entry' in p else 1.0)

                self.save_balance(); self.save_state()
                self._render_dashboard(ts, macro_data, miro_data, asset_signals, yield_info, usdt_data, xaut_data, agent_res)
                
            except Exception as e: print(f"Error: {e}")
            await asyncio.sleep(30)

async def main(bot):
    await bot.exchange.initialize() if hasattr(bot.exchange, 'initialize') else None
    supervisor = WebSocketSupervisor(bot)
    asyncio.create_task(supervisor.start())
    asyncio.create_task(bot._train_initial_evo_pop())
    await bot.run_async()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', type=str, default='backtest')
    args = parser.parse_args()
    bot = MulticoreMasterBot(mode=args.mode)
    asyncio.run(main(bot))
