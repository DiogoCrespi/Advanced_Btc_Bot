# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import time
import gc
import os
import sys
import orjson
import uvloop
import requests
import queue
import threading
import argparse
import numpy as np
import pandas as pd
import asyncio
import socket
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
from logic.feature_store import FeatureStore
from logic.tribunal import ConsensusTribunal
from logic.tv_connector import TVConnector
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
    if isinstance(obj, datetime): return obj.isoformat()
    return str(obj)

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

        self.trade_amount = 200.0
        self.fee_rate = 0.001
        self.take_profit = 0.03
        self.stop_loss = 0.015
        self.min_binance_amount = 10.0
        self.balance_file = "results/balance_state.txt"
        # IPC Router (Fase 5)
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
        self.tv_connector = TVConnector()
        self.risk_manager = RiskManager()
        self.ledger = Ledger()
        self.limit_executor = LimitExecutor(self.exchange)
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.use_mirofish = False # MiroFish desativado permanentemente em favor do LocalOracle
        self.listen_key = None
        self.last_balance_sync = datetime.now()
        self.shadow_mode = os.getenv("SHADOW_MODE", "True").lower() == "true"
        self.enable_ai = os.getenv("ENABLE_AI", "True").lower() == "true"
        
        if self.shadow_mode:
            print("[BOOT] MODO SHADOW ATIVADO: Nenhuma ordem real sera enviada.")
        if not self.enable_ai:
            print("[BOOT] INTELIGENCIA ARTIFICIAL DESATIVADA via .env")
        
        # Persistence & Maturity
        self.feature_store = FeatureStore()
        
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
        self.executor = ThreadPoolExecutor(max_workers=20) # Aumentado para 20 (6 ativos + Oracle + Macro + Fallbacks)
        self.process_executor = ProcessPoolExecutor(max_workers=4, max_tasks_per_child=10) # Aumentado para 4 (T1600 Multicore)

        self.liquidity_mult = {"BTCBRL":1.0, "ETHBRL":0.95, "SOLBRL":0.85, "LINKBRL":0.8, "AVAXBRL":0.8, "RENDERBRL":0.75}
        # Sincronizacao de persistencia: Prioridade para o Ledger (SQLite)
        self.usdt_balance = 0.0
        self.xaut_balance = 0.0
        # Forcar balanco de Batedor (Reset para R$ 1000)
        self.balance = 1000.0
        self.save_balance()
        
        # Garantir que todos os ativos existam no dicionario de posicoes (Anti-KeyError)
        self.positions = self.ledger.load_active_positions()
        if not self.positions: 
            self.positions = self.load_state()
            
        for asset in assets:
            if asset not in self.positions:
                self.positions[asset] = []
        
        self.total_equity = self.balance
        self.dashboard_logs = deque(maxlen=5)
        self.last_status_report = datetime.now() - timedelta(hours=3, minutes=55) # Primeiro report em 5 min
        self.audit_metrics = {"n": 0, "slippage": 0.0, "gap": 0.0, "pf": 0.0}
        self.last_usdt_trade = datetime.now() - timedelta(hours=1)
        
        print(f"[INIT] Booting Multicore Brains ({self.mode})...")
        os.makedirs("models", exist_ok=True)
        
        # Warmup Buffer
        history_df = self.feature_store.load_history()
        
        if self.enable_ai:
            for asset in assets:
                # Prioriza o modelo v2_massive para BTCUSDT se existir
                massive_path = f"models/{asset.lower()}_brain_v2_massive.pkl"
                model_path = f"models/{asset.lower()}_brain_v1.pkl"
                
                brain = self.brains[asset]
                
                # 1. Carregar Modelo (Prioriza Massive -> V1)
                if os.path.exists(massive_path):
                    print(f"[BOOT] {asset}: Carregando Modelo GOLD STANDARD (v2_massive)...")
                    brain.load_model(massive_path)
                else:
                    print(f"[BOOT] {asset}: Carregando Modelo v1...")
                    brain.load_model(model_path)
                
                # 2. Maturidade dos Dados & Backfill
                asset_history = history_df[history_df['symbol'] == asset] if not history_df.empty and 'symbol' in history_df.columns else pd.DataFrame()
                
                if len(asset_history) < 10000 and self.mode != "backtest":
                    print(f"[BOOT] {asset}: Dados insuficientes ({len(asset_history)}). Iniciando Backfill...")
                    new_data = self.engine.fetch_historical_backfill(asset, target_samples=10000)
                    if not new_data.empty:
                        new_data['symbol'] = asset
                        self.feature_store.append_new_data(new_data)
                        asset_history = new_data
                
                # 3. Treinamento/Ajuste (se necessario)
                if not brain.is_trained or brain.n_samples < 2000:
                    print(f"[BOOT] {asset}: Treinando com dataset maturado ({len(asset_history)} amostras)...")
                    if not asset_history.empty:
                        asset_history = self.engine.apply_indicators(asset_history)
                        score = brain.train(asset_history, train_full=True, tp=self.take_profit, sl=self.stop_loss)
                        brain.save_model(model_path)
                        self.stats[asset]["oos_score"] = score
                else:
                    print(f"[BOOT] {asset}: Modelo LIVE pronto (Samples: {brain.n_samples} | Status: {brain.status})")

                # 4. v3-Alpha Shadow Load
                shadow_path = f"models/brain_rf_v3_alpha_{asset}.pkl"
                if self.shadow_brains[asset].load_model(shadow_path):
                    print(f"[BOOT] {asset}: Modelo Shadow v3-Alpha Ativo.")
                else:
                    print(f"[WARN] {asset}: Shadow v3-Alpha nao encontrado.")
        else:
            print("[BOOT] Pulando Boot de Modelos (IA Desativada)")

    async def _update_audit_metrics_loop(self):
        """
        Consulta o Neo4j periodicamente para atualizar o dashboard de reconciliacao.
        Respeita o Code Freeze: Apenas leitura de telemetria.
        """
        while True:
            if self.memory.driver:
                try:
                    with self.memory.driver.session() as session:
                        query = """
                        MATCH (o:Outcome)-[:FOLLOWED]->(d:Decision)
                        WITH count(o) as n,
                             avg(abs(d.signal_price - o.actual_entry_price)/d.signal_price) as slippage,
                             sum(CASE WHEN o.pnl_real > 0 THEN o.pnl_real ELSE 0 END) as gross_profit,
                             abs(sum(CASE WHEN o.pnl_real < 0 THEN o.pnl_real ELSE 0 END)) as gross_loss,
                             avg(o.pnl_real) as net_expectancy
                        RETURN n, slippage, net_expectancy, 
                               CASE WHEN gross_loss = 0 THEN 999.0 ELSE gross_profit / gross_loss END as survival_pf
                        """
                        res = session.run(query).single()
                        if res and res["n"] > 0:
                            self.audit_metrics["n"] = res["n"]
                            self.audit_metrics["slippage"] = res["slippage"] or 0.0
                            self.audit_metrics["pf"] = res["survival_pf"] or 0.0
                            self.audit_metrics["gap"] = res["net_expectancy"] or 0.0
                except Exception: pass
            await asyncio.sleep(600) # 10 minutos

    async def _periodic_retrain_loop(self):
        """
        Pipeline de Retreino Automatizado (Frequencia: 24h).
        Garante que o bot se adapte a novos regimes de volatilidade.
        """
        while True:
            await asyncio.sleep(60 * 60 * 24) # 24 horas
            print("[ML-PIPELINE] Iniciando ciclo de retreino diario...")
            try:
                for asset in self.assets:
                    print(f"[ML-PIPELINE] Atualizando modelo para {asset}...")
                    new_data = self.engine.fetch_historical_backfill(asset, target_samples=10000)
                    if not new_data.empty:
                        new_data['symbol'] = asset
                        self.feature_store.append_new_data(new_data)
                        brain = self.brains[asset]
                        # Treinamento In-Memory com novo dataset
                        score = await asyncio.get_event_loop().run_in_executor(
                            self.process_executor, brain.train, new_data
                        )
                        model_path = f"models/{asset.lower()}_brain_v1.pkl"
                        brain.save_model(model_path)
                        print(f"[ML-PIPELINE] {asset} atualizado. Novo Score: {score:.2f}")
                self.notify_telegram("🔄 Ciclo de retreino diario concluido com sucesso.", title="PIPELINE")
            except Exception as e:
                print(f"[ML-PIPELINE] Erro no retreino: {e}")



        # Background tasks moved to main() to avoid "no running event loop" error

    def _log_worker(self):
        while True:
            item = self.log_queue.get()
            if item is None: break
            try:
                # Reparação: Unpacking defensivo (Hotfix v3-Alpha)
                if not isinstance(item, tuple) or len(item) < 2:
                    print(f"[LOG_WORKER] Item malformado ignorado: {item}")
                    continue

                action = item[0]
                payload = item[1]

                if action == "append":
                    path, content = payload
                    with open(path, "a", encoding="utf-8") as f: f.write(content + "\n")
                elif action == "write":
                    path, content = payload
                    with open(path, "w", encoding="utf-8") as f: f.write(content)
                elif action == "save_state":
                    path, content = payload
                    with open(path, "wb") as f: 
                        f.write(orjson.dumps(content, option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_INDENT_2, default=orjson_default))
            except Exception as e:
                print(f"[LOG_WORKER] Erro critico: {e} | Item: {item}")
            finally:
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
                    s = orjson.loads(f.read())
                    self.usdt_balance = s.get("usdt_balance", 0.0)
                    self.xaut_positions = s.get("xaut_positions", [])
                    self.caution_mode = s.get("caution_mode", False)
                    l_usdt = s.get("last_usdt_trade_iso")
                    if l_usdt: self.last_usdt_trade = datetime.fromisoformat(l_usdt.decode() if isinstance(l_usdt, bytes) else l_usdt)
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
                "last_usdt_trade_iso": self.last_usdt_trade.isoformat(),
                "reliability_stats": rel_stats
            }
        # IPC Otimizado: Envia trigger leve para o worker persistir o estado em background
        # O worker reconstruira o estado final a partir do DB ou snapshot de memoria
        self.log_queue.put(("save_state_trigger", self.status_file))

    async def sync_balances_from_exchange(self):
        """Sincronizacao forçada via REST API para evitar deriva de saldo."""
        if self.mode == "backtest" or self.shadow_mode: return
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

    def _render_dashboard(self, ts, macro_data, miro_data, asset_signals, yield_info, usdt_data, xaut_data, agent_res, pos_value=0.0):
        """Builds the stylized console UI as requested by the user."""
        header = f"+{'-'*80}+\n"
        header += f"| >>> ADVANCED MULTICORE BTC BOT | {ts} | Equity: R$ {self.total_equity:,.2f} |\n"
        header += f"| Saldo Disponivel: R$ {self.balance:,.2f} | Ativos: R$ {pos_value:,.2f} | USDT: {self.usdt_balance:.2f} |\n"
        
        m_mult, m_msg = self.agent.radar.get_recommended_position_mult()
        header += f"| Macro Risk Score: {self.macro_risk:.2f} | Recommendation: {m_msg} |\n"
        header += f"+{'-'*80}+\n"
        
        # Portfolio consolidado por ativo
        port_lines = []
        for asset, pos_list in self.positions.items():
            if not pos_list: continue
            
            total_cost = sum(p['cost'] for p in pos_list)
            total_qty = sum(p['qty'] for p in pos_list)
            avg_entry = total_cost / total_qty if total_qty > 0 else 0
            curr_price = asset_signals.get(asset,{}).get('price', avg_entry)
            signal = pos_list[0]['signal']
            
            total_pnl_pct = (curr_price / avg_entry - 1) * signal if avg_entry > 0 else 0
            total_val = total_cost * (1 + total_pnl_pct)
            
            total_pnl_nominal = total_val - total_cost
            pyramid_info = f"[x{len(pos_list)}]" if len(pos_list) > 1 else "    "
            port_lines.append(f"| {asset:8} {pyramid_info:4} ({signal:2}) @{avg_entry:9.1f} | Val: R${total_val:8.2f} | PnL:{total_pnl_pct:+6.2%} ({total_pnl_nominal:+6.2f}) |")
        
        portfolio = f"| [PORTFOLIO] Ativos Consolidados ({len(port_lines)}) R${pos_value:,.2f}".ljust(79) + "|\n"
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
        
        # Audit Engine (Incubacao)
        n_aud = self.audit_metrics["n"]
        slip = self.audit_metrics["slippage"]
        pf_aud = self.audit_metrics["pf"]
        status_audit = "✅ ESTAVEL" if pf_aud > 1.05 else "⚠️ DEGRADACAO"
        if n_aud < 30: status_audit = f"⏳ INCUBACAO ({n_aud}/30)"
        
        audit = f"| [AUDIT ENGINE] Status: {status_audit:20} | PF Real: {pf_aud:.2f} |\n"
        gap = self.audit_metrics["gap"]
        audit += f"| Avg Slippage: {slip:.4%} | Realized Expectancy: {gap:+.4%} | N: {n_aud} |\n"
        audit += f"+{'-'*80}+\n"

        # Oracle Local
        miro_sent = miro_data.get('sentiment', 'Neutral')
        miro_conf = miro_data.get('confidence', 0.5)
        miro_score = miro_conf if miro_sent == "Bullish" else (-miro_conf if miro_sent == "Bearish" else 0)
        
        status_oraculo = "ATIVADO (LocalOracle)" if self.enable_ai else "DESATIVADO"
        miro = f"[ORACLE LOCAL] Personas Reportam: {miro_sent} ({miro_conf:.0%}) | Mult: {self.oracle_state.get('multiplier',1.0):.2f} [{status_oraculo}]\n"
        
        # Composite
        full = header + portfolio + yield_s + usdt_s + alpha + xaut_s + logs + audit + miro
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
            # Limita a compra de USDT para evitar spam no log e over-allocation (CUIDADO: Cooldown de 10 min e Teto de 500 USDT)
            if sig == 1 and self.balance >= 100 and self.usdt_balance < 500 and (datetime.now() - self.last_usdt_trade).total_seconds() > 600:
                self.last_usdt_trade = datetime.now()
                self.balance -= 100
                self.usdt_balance += 100 / price
                self.async_log(self.log_file, f"[USDT BUY] BRL 100 -> {100/price:.2f} USDT @ {price:.2f}")
                self.save_balance(); self.save_state()
            elif sig == -1 and self.usdt_balance > 10:
                old_usdt = self.usdt_balance
                self.balance += self.usdt_balance * price * 0.999
                self.usdt_balance = 0
                self.async_log(self.log_file, f"[USDT SELL] {old_usdt:.2f} USDT -> BRL @ {price:.2f}")
                self.last_usdt_trade = datetime.now()
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
        
        # Carrega historico para treinamento maturado da evolucao
        history_df = self.feature_store.load_history()

        # 1. Train Main Brains (Somente se nao estiverem maturados)
        for asset in self.assets:
            brain = self.brains[asset]
            if not brain.is_trained or brain.n_samples < 2000:
                df = await loop.run_in_executor(self.executor, self.engine.fetch_binance_klines, asset, "1h", 1000)
                if not df.empty:
                    df = self.engine.apply_indicators(df)
                    tasks.append(loop.run_in_executor(self.executor, brain.train, df))
        
        # 2. Train Shadow Brains (Somente se nao estiverem maturados)
        for asset in self.assets:
            brain = self.shadow_brains[asset]
            if not brain.is_trained or brain.n_samples < 2000:
                df = await loop.run_in_executor(self.executor, self.engine.fetch_binance_klines, asset, "1h", 1000)
                if not df.empty:
                    df = self.engine.apply_indicators(df)
                    tasks.append(loop.run_in_executor(self.executor, brain.train, df))

        # 3. Train Evo Brains (Limitado ao Top 2 para reduzir carga de CPU no boot)
        print(f"[INIT] Treinando Top 2 DNAs da Populacao Evolutiva ({len(self.assets)} ativos cada)...")
        for asset in self.assets:
            # Pre-processa os dados UMA VEZ por ativo usando o cerebro principal
            main_brain = self.brains[asset]
            df_asset = await loop.run_in_executor(self.executor, self.engine.fetch_binance_klines, asset, "1h", 2000)
            if df_asset.empty: continue
            
            data_clean = main_brain.prepare_features(df_asset)
            f_cols = [c for c in data_clean.columns if c.startswith('feat_') and 'imbalance' not in c]
            X_clean = data_clean[f_cols].values
            y_clean = main_brain.create_labels(data_clean)
            
            min_l = min(len(X_clean), len(y_clean))
            X_final = X_clean[:min_l]; y_final = y_clean[:min_l]

            for dna in self.evo_engine.population[:2]:
                brain = self.evo_brains[dna.id][asset]
                # Reparação: Injeta a matriz matemática exata já higienizada
                await loop.run_in_executor(self.executor, brain.train, None, False, None, None, None, X_final, y_final)
                await asyncio.sleep(0.1)
        
        print("[INIT] Treinamento de background concluido.")

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
                    if macro_data is None: macro_data = {'dxy_change': 0, 'sp500_change': 0, 'gold_change': 0}
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
                        f_risk = 0.0 # Default failure risk
                        
                        # Brains candidates
                        live_brain = self.brains[asset]
                        shadow_brain = self.shadow_brains[asset]
                        
                        # Identify Alfa for Ancestral vote
                        alfa_dna = self.evo_engine.population[0]
                        ancestral_brain = self.evo_brains[alfa_dna.id][asset]

                        # Fetch live market microstructure (PR #60) - VETO Logic
                        imbalance = await loop.run_in_executor(self.executor, self.engine.fetch_order_book_imbalance, asset)
                        
                        # (IPC Broadcast to Scout Bot removed - Architecture Unified)


                        # Parallelize predictions across ProcessPoolExecutor
                        if self.enable_ai:
                            tasks = [
                                loop.run_in_executor(self.process_executor, _cpu_heavy_predict, live_brain, df.copy(), self.macro_risk, self.btc_dominance, 0.38),
                                loop.run_in_executor(self.process_executor, _cpu_heavy_predict, shadow_brain, df.copy(), self.macro_risk, self.btc_dominance, 0.38),
                                loop.run_in_executor(self.process_executor, _cpu_heavy_predict, ancestral_brain, df.copy(), self.macro_risk, self.btc_dominance, 0.38)
                            ]
                            
                            results = await asyncio.gather(*tasks)
                            (sig, prob, reason, price, rel, atr) = results[0]
                            (s_sig, s_prob, s_reason, _, _, _) = results[1]
                            ancestral_sig = int(results[2][0])
                            ancestral_prob = results[2][1]
                        else:
                            # AI Disabled: Neutral signals
                            price = float(df['close'].iloc[-1])
                            sig, prob, reason, rel, atr = 0, 0.5, "AI_DISABLED", 1.0, 0.0
                            s_sig, s_prob, s_reason = 0, 0.5, "AI_DISABLED"
                            ancestral_sig, ancestral_prob = 0, 0.5

                        
                        # 4. Consenso Externo (TradingView) - Quarentena Sniper
                        tv_sig = await loop.run_in_executor(self.executor, self.tv_connector.get_technical_summary, asset)
                        
                        # Logging Shadow Decision (Enriched for Audit)
                        if s_sig != 0:
                            print(f"[SHADOW-v3] {asset}: Sinal {s_sig} | Prob: {s_prob:.1%} | Reason: {s_reason}")
                            # Passamos vol e trend capturados do DataEngine para o Grafo
                            metrics = {"reason": s_reason, "vol": atr, "trend": rel}
                            self.memory.record_shadow_decision(asset, s_sig, price, s_prob, metrics, tv_signal=tv_sig)

                        t_sigs = {'live': {'sig': int(sig), 'prob': prob, 'reason': reason}, 'shadow': {'sig': int(s_sig), 'prob': s_prob, 'reason': s_reason}, 'ancestral': {'sig': ancestral_sig, 'prob': ancestral_prob}}
                        
                        # So permite o voto do TV se estivermos no modo Scout (Stress Lab / Low Vol)
                        is_scout_mode = "[LOW_VOL]" in (s_reason or "") or "[LOW_VOL]" in (reason or "")
                        safe_tv_sig = int(tv_sig) if is_scout_mode else 0
                        
                        fsig, fconf, treason = self.tribunal.evaluate_signals(t_sigs, {}, failure_risk=f_risk, macro_status=self.macro_status, tv_signal=safe_tv_sig)
                        
                        # PATCH: Se o sinal for isolado e vier do v3-Alpha, preservar a razao para o StrategistAgent
                        if "v3-Alpha" in s_reason and fsig == s_sig and "Sinal Isolado" in treason:
                            treason = s_reason
                        
                        acc = self.stats.get('global_acc_4h', 0.5)
                        conv = (fconf * acc) * self.liquidity_mult.get(asset, 0.5)
                        
                        with signals_lock:
                            asset_signals[asset] = {
                                'signal': int(fsig), 
                                'prob': fconf, 
                                'conviction': conv, 
                                'reason': treason, 
                                'price': price,
                                'reliability': rel,
                                'atr': atr,
                                'imbalance': imbalance,
                                'status': live_brain.status

                            }
                            # Sync incrementally to feature store
                            if iter_count % 10 == 0:
                                last_row = df.tail(1).copy()
                                last_row['symbol'] = asset
                                self.feature_store.append_new_data(last_row)
                                
                            if fsig != 0: self.signal_history[asset].append({'ts':datetime.now(), 'sig':fsig, 'price':price, 'metrics':{}})
                    except Exception as e:
                        print(f"[ERROR] Falha scan {asset}: {e}")
                    finally:
                        # Limpeza de Memoria (Anti-Leak)
                        if 'df' in locals(): del df
                        if 'tasks' in locals(): del tasks
                        if 'results' in locals(): del results
                        gc.collect()

                await asyncio.gather(*(scan_asset(a) for a in self.assets))
                
                # Agent Decision (v3-Alpha: Filtragem Rigida de Expectancia)
                # Somente sinais com Probabilidade >= 55% sao contabilizados para o consenso global
                valid_signals = {a: s for a, s in asset_signals.items() if s['prob'] >= 0.55}
                tier2 = sum([s['signal'] for s in valid_signals.values()])
                
                agent_macro = macro_data.copy()
                agent_macro['news_sentiment'] = news_sent
                agent_res = self.agent.run({'tier2': tier2}, agent_macro)
                if not agent_res or 'allocation_mult' not in agent_res:
                    print("[WARN] StrategistAgent não retornou resultado válido. Pulando ciclo...")
                    continue
                final_mult = agent_res['allocation_mult']
                
                # Loop de Execucao
                for asset, s in asset_signals.items():
                    active = self.positions.get(asset, [])
                    if not isinstance(active, list): active = [active] if active else []
                    
                    rem = []
                    for p in active:
                        is_p_shadow = p.get('is_shadow', False)
                        pnl = (s['price']/p['entry'] - 1) * p['signal']
                        exit_r = None
                        if s['signal'] == -p['signal'] and s['prob'] >= 0.75: exit_r = "REVERSAL"
                        if is_extreme and asset != "BTCBRL": exit_r = "BUNKER_EXIT"
                        
                        act, r_reason = self.risk_manager.check_exit_conditions(asset, p.get('id','0'), s['price'], p['entry'], p['signal'], "HOLD", atr_value=s.get('atr'))
                        if exit_r or act == 'SELL':
                            if self.shadow_mode or is_p_shadow:
                                # Shadow Settlement - Restore capital + simulated PnL
                                returned = p['cost'] * (1 + pnl - 0.001)  # fee simulada de 0.1%
                                self.balance += returned
                                self.save_balance()
                                print(f"[SHADOW] Liquidando {asset} @ {s['price']} ({pnl:+.2%}) | Retorno: R$ {returned:.2f}")
                                self.ledger.close_position(asset)
                                self.ledger.record_completed_trade(asset, "SELL" if p['signal']==1 else "BUY", p['entry'], s['price'], p['qty'], pnl, p['cost']*pnl, p['time'], exit_r or r_reason, is_shadow=True)
                                self.memory.settle_shadow_outcome(p.get('did'), s['price'], pnl)
                                self.notify_telegram(f"[SHADOW] FECHADO {asset}: {exit_r or r_reason} ({pnl:+.2%})")
                            else:
                                # Real Execution
                                qty = p['qty']
                                side = SIDE_SELL if p['signal'] == 1 else SIDE_BUY
                                print(f"[EXEC] Saindo de {asset} via Limit Order...")
                                order = await self.limit_executor.execute_limit_order(asset, side, qty)
                                if order:
                                    final_price = float(order.get('price', s['price']))
                                    pnl_real = (final_price/p['entry'] - 1) * p['signal']
                                    self.balance += p['cost'] * (1 + pnl_real - 0.001)
                                    self.ledger.close_position(asset)
                                    self.ledger.record_completed_trade(asset, side, p['entry'], final_price, qty, pnl_real, p['cost']*pnl_real, p['time'], exit_r or r_reason)
                                    self.memory.record_trade(asset, side, qty, final_price)
                                    self.memory.record_outcome(pnl_real)
                                    self.save_balance()
                                    self.notify_telegram(f"FECHADO {asset}: {exit_r or r_reason} ({pnl_real:+.2%}) @ {final_price}")
                        else: rem.append(p)
                    self.positions[asset] = rem

                    # Entries — Pyramiding com Trava de Expectancia (v3-Alpha)
                    MAX_PYRAMID = 3 
                    existing = self.positions[asset]
                    existing_signal = existing[0]['signal'] if existing else None
                    same_direction = (existing_signal == s['signal']) if existing_signal else True
                    
                    # Reparação: Pyramiding exige confluência Macro e Edge estatístico provado
                    # Reparação: Travas Aliviadas para modo Batedor (Data Collection)
                    pf_real = self.audit_metrics["pf"]
                    acc_real = self.brains["BTCBRL"].reliability_score
                    
                    # Travas reduzidas: PF > 1.0 e Acc > 0.45 (Era 1.05 e 0.52)
                    can_pyramid = (len(existing) > 0 and len(existing) < MAX_PYRAMID and same_direction and 
                                   pf_real >= 1.0 and acc_real > 0.45)
                    
                    # Entrada facilitada: Prob >= 0.48 (Era 0.55)
                    allow_entry = (s['signal'] != 0) and (len(existing) == 0) and (s['prob'] >= 0.48)

                    if allow_entry:
                        if can_pyramid:
                            print(f"[PYRAMID] {asset}: Adicionando aporte #{len(existing)+1} (Sinal: {s['signal']} | Prob: {s['prob']:.1%})")
                        
                        # 4. Hybrid Entry Logic (Batedor v3)
                        dec, ar, smod = self.agent.assess_trade(
                            asset, s['signal'], s['prob'], s['reason'], 
                            reliability=s.get('reliability', 1.0), 
                            caution_mode=self.caution_mode,
                            book_imbalance=s.get('imbalance', 0.0)
                        )
                        
                        # Tiered Sizing Logic (Reset para R$ 1000 de banca)
                        if dec == "APPROVE_SCOUT":
                            sizing = 10.0 # Batedor (Minimo para coletar dados)
                        elif dec.startswith("APPROVE"):
                            # Sniper / Standard (Usa R$ 200 ou Kelly calibrado)
                            sizing = 200.0 # Aporte padrao solicitado pelo usuario
                            sizing = min(sizing, self.balance * 0.5) # Protecao minima de margem
                            
                        if dec.startswith("APPROVE") and sizing >= 10 and self.balance >= sizing:
                            # Per-model shadow (Observation) vs Bot-wide shadow mode
                            model_shadow = s.get('status') == "OBSERVATION"
                            
                            if model_shadow:
                                print(f"👻 [SHADOW-OBS] {asset}: Entrada simulada (Maturidade Insuficiente).")
                                self.memory.record_context_and_decision(news_sent, self.macro_risk, f"SHADOW_ALPHA_{asset}_{s['signal']}")
                            elif self.shadow_mode:
                                # Global Shadow Mode
                                side = SIDE_BUY if s['signal'] == 1 else SIDE_SELL
                                qty = await self.format_quantity_async(asset, sizing / s['price'])
                                self.balance -= sizing
                                self.save_balance()
                                print(f"[SHADOW-BATEDOR] Abrindo {asset} @ {s['price']} | Custo: R$ {sizing:.2f} | Saldo: R$ {self.balance:.2f}")
                                did = self.memory.record_shadow_decision(asset, side, s['price'], s['prob'], self.last_regime_metrics)
                                pos_data = {
                                    "entry": s['price'], "signal": s['signal'], "qty": qty, 
                                    "cost": sizing, "time": datetime.now().isoformat(), "did": did, "is_shadow": True
                                }
                                self.positions[asset].append(pos_data)
                                self.ledger.save_active_position(asset, pos_data, is_shadow=True)
                                self.notify_telegram(f"[SHADOW] ABERTO {asset}: {side} @ {s['price']} | R$ {sizing:.2f}")
                            else:
                                # Real Entry
                                side = SIDE_BUY if s['signal'] == 1 else SIDE_SELL
                                qty = await self.format_quantity_async(asset, sizing / s['price'])
                                print(f"[EXEC-BATEDOR] Entrando em {asset} via Limit Order...")
                                order = await self.limit_executor.execute_limit_order(asset, side, qty)
                                if order:
                                    actual_price = float(order.get('price', s['price']))
                                    actual_sizing = qty * actual_price
                                    self.balance -= actual_sizing
                                    did = self.memory.record_shadow_decision(asset, side, s['price'], s['prob'], {
                                        "tp": 0.015, "sl": 0.008, "horizon": 4, "reason": "Batedor Execution"
                                    })
                                    pos_data = {
                                        "entry": actual_price, "signal": s['signal'], "qty": qty, 
                                        "cost": actual_sizing, "time": datetime.now().isoformat(),
                                        "order_id": order.get('orderId'), "is_shadow": False,
                                        "decision_id": did, "signal_price": s['price']
                                    }
                                    self.positions[asset].append(pos_data)
                                    self.ledger.save_active_position(asset, pos_data)
                                    self.memory.record_trade(asset, side, qty, actual_price)
                                    self.notify_telegram(f"ABERTO {asset}: {side} {qty} @ {actual_price} | R$ {actual_sizing:.2f}")
                                    self.save_balance(); self.save_state()

                        else:
                            if not dec.startswith("APPROVE"):
                                print(f"[STRATEGIST] Rejeitado {asset}: {ar}")
                            elif sizing < 10 and sizing > 0:
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

                # Calculate Total Equity (Balance + USDT + Portfolio)
                pos_value = 0.0
                for asset, pos_list in self.positions.items():
                    for p in pos_list:
                        # Prioriza o preço do asset_signals (mais fresco/REST) sobre o live_prices (WebSocket)
                        p_price = asset_signals.get(asset, {}).get('price', self.live_prices.get(asset, p['entry']))
                        p_pnl = (p_price / p['entry'] - 1) * p['signal']
                        pos_value += p['cost'] * (1 + p_pnl)
                
                self.total_equity = self.balance + (usdt_data['price'] * usdt_data['balance']) + pos_value
                
                # Add XAUT value to equity (converting BTC to BRL)
                btc_price = asset_signals.get("BTCBRL", {}).get("price", 0.0)
                if btc_price == 0.0 and "BTCBRL" in self.live_prices:
                    btc_price = self.live_prices["BTCBRL"]
                
                # Fallback absolute price for calculation if still 0
                eff_btc_price = btc_price if btc_price > 0 else 350000.0
                
                with self.xaut_lock:
                    for xp in self.xaut_positions:
                        # cost_btc * eff_btc_price * (curr_ratio / entry_ratio)
                        curr_ratio = xaut_data['ratio']
                        entry_ratio = xp.get('ratio_entry', curr_ratio)
                        xp_val_btc = xp['cost_btc'] * (curr_ratio / entry_ratio)
                        self.total_equity += xp_val_btc * eff_btc_price

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
                self._render_dashboard(ts, macro_data, miro_data, asset_signals, yield_info, usdt_data, xaut_data, agent_res, pos_value=pos_value)
                
                # Relatorio Periodico (Heartbeat) - Cada 4 horas
                if datetime.now() - self.last_status_report > timedelta(hours=4):
                    pos_count = sum(len(p) if isinstance(p, list) else 1 for p in self.positions.values() if p)
                    status_msg = f"🛡️ <b>STATUS:</b> Equity R$ {self.total_equity:,.2f} | Ativos R$ {pos_value:,.2f} | Saldo R$ {self.balance:,.2f} | Pos: {pos_count} | 🕒 {ts} | ✅ Normal"
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
    if bot.enable_ai:
        asyncio.create_task(bot._train_initial_evo_pop())
        # Pipeline de Retreino Automatizado (24h)
        asyncio.create_task(bot._periodic_retrain_loop())
        # Telemetria de Auditoria
        asyncio.create_task(bot._update_audit_metrics_loop())
    if bot.enable_ai:
        asyncio.create_task(bot.oracle.start_loop())
    else:
        print("[INIT] Ignorando Oracle Loop (IA Desativada)")
    await bot.run_async()

if __name__ == "__main__":
    # Injeção de UVLOOP para máxima performance TCP/WebSocket
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', type=str, default='backtest')
    args = parser.parse_args()
    bot = MulticoreMasterBot(mode=args.mode)
    asyncio.run(main(bot))
