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
from binance.client import AsyncClient
from binance import BinanceSocketManager
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
        while self._is_running:
            try:
                await self._run_socket_session()
                self._backoff_delay = 1
            except Exception as e:
                self.logger.error(f"[SUPERVISOR] Queda critica: {e}")
                await self._handle_reconnection()

    async def _run_socket_session(self):
        if not self.bot.client:
            await asyncio.sleep(5)
            raise Exception("Binance Client nulo")
        bm = BinanceSocketManager(self.bot.client)
        streams = [f"{s.lower()}@ticker" for s in self.bot.assets]
        if "usdtbrl@ticker" not in streams: streams.append("usdtbrl@ticker")
        async with bm.multiplex_socket(streams) as stream:
            while True:
                res = await asyncio.wait_for(stream.recv(), timeout=15)
                if res and 'data' in res:
                    data = res['data']; symbol = data['s']
                    self.bot.live_prices[symbol] = float(data['c'])
                self._backoff_delay = 1

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
        try:
            requests.post(f"{self.ntfy_url}/{self.ntfy_topic}", data=msg.encode('utf-8'), headers={"Title": title}, timeout=5)
        except Exception: pass

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

    def _process_usdt(self, ts):
        lines = []
        df = self.engine.fetch_usdt_brl_data(limit=100)
        if df.empty: return ["| [USDT] Sem dados |"]
        price = float(df['close'].values[-1])
        sig, conf, reason = self.usdt_logic.get_signal(df, self.macro_risk)
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
        lines.append(f"| [USDT/BRL] Preco: {price:.2f} | Saldo: {self.usdt_balance:.2f} USDT |")
        return lines

    def _process_xaut(self, ts):
        lines = []
        df = self.engine.fetch_xaut_ratio(limit=100)
        if df.empty: return ["| [XAUT] Sem dados |"]
        ratio = float(df['close'].values[-1])
        with self.xaut_lock:
            rem = []
            for p in self.xaut_positions:
                pnl = (ratio / p['ratio_entry'] - 1)
                if pnl > 0.04 or pnl < -0.02: self.async_log(self.xaut_log, f"FECHADO XAUT: {pnl:.2%}")
                else: rem.append(p)
            self.xaut_positions = rem
        lines.append(f"| [XAUT/BTC] Ratio: {ratio:.6f} | Pos: {len(self.xaut_positions)} |")
        return lines

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
                        df = await loop.run_in_executor(self.executor, self.engine.fetch_binance_klines, asset, "1h", 200)
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

                self._process_usdt(ts)
                self._process_xaut(ts)
                self.save_balance(); self.save_state()
                print(f"| [{ts}] Equity: R$ {self.balance:.2f} | Risk: {self.macro_risk:.2f} |")
                
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
