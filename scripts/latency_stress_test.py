import asyncio
import os
import time
import numpy as np
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from data.data_engine import DataEngine
from logic.database.ledger import Ledger

class StressTester:
    def __init__(self, assets=["BTCBRL", "ETHBRL", "SOLBRL", "LINKBRL", "AVAXBRL", "RENDERBRL"]):
        self.assets = assets
        self.engine = DataEngine()
        # Isolamento: Banco em memoria para nao poluir a producao
        # Evitar erro de makedirs com :memory:
        self.mock_ledger = Ledger(db_path="results/stress_test_mock.db")
        # Remover se ja existir
        if os.path.exists("results/stress_test_mock.db"):
            os.remove("results/stress_test_mock.db")
        self.executor = ThreadPoolExecutor(max_workers=10)

    async def simulate_burst(self):
        print(f"\n🚀 Iniciando Teste de Concorrência Extrema (Burst de {len(self.assets)} ativos)...")
        
        latencies = []
        start_time = time.perf_counter()
        
        # Tarefas concorrentes: Fetch Order Book + Decision (Simulada) + Persistence
        tasks = [self._process_mock_trade(asset) for asset in self.assets]
        
        results = await asyncio.gather(*tasks)
        
        total_time = (time.perf_counter() - start_time) * 1000
        latencies = [r['latency'] for r in results]
        
        self._report_metrics(latencies, total_time, results)

    async def _process_mock_trade(self, asset):
        t_start = time.perf_counter()
        
        # 1. API Check (Microestrutura)
        # Simulando a carga real de snapshot do book
        try:
            loop = asyncio.get_event_loop()
            imbalance = await loop.run_in_executor(self.executor, self.engine.fetch_order_book_imbalance, asset)
            api_status = "SUCCESS"
        except Exception as e:
            imbalance = 0
            api_status = f"FAILED ({str(e)})"

        # 2. Persistencia Sintetica (SQLite em Memoria)
        # Simulando o registro de uma decisao e abertura de posicao
        trade_data = {
            "entry": 50000.0, "signal": 1, "qty": 0.01, 
            "cost": 500.0, "time": datetime.now().isoformat(), "is_shadow": True
        }
        self.mock_ledger.save_active_position(asset, trade_data, is_shadow=True)
        
        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000
        
        return {
            'asset': asset,
            'latency': latency_ms,
            'api_status': api_status,
            'imbalance': imbalance
        }

    def _report_metrics(self, latencies, total_time, results):
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        avg = np.mean(latencies)
        
        print("\n" + "="*50)
        print("📊 RELATÓRIO DE ESTRESSE SINTÉTICO (P99 LATENCY)")
        print("="*50)
        print(f"Tempo Total do Burst (RTT): {total_time:.2f} ms")
        print(f"Latência Média por Ativo:   {avg:.2f} ms")
        print(f"Percentil P95:             {p95:.2f} ms")
        print(f"Percentil P99:             {p99:.2f} ms")
        print("-" * 50)
        
        success_count = sum(1 for r in results if r['api_status'] == "SUCCESS")
        print(f"Sucesso API (Order Book):    {success_count}/{len(self.assets)}")
        
        print("\nDetalhamento por Ativo:")
        for r in results:
            print(f"  > {r['asset']:9} | Latency: {r['latency']:6.2f}ms | Imbalance: {r['imbalance']:>6.2f} | API: {r['api_status']}")
        
        print("\n[DIAGNÓSTICO]")
        if p99 < 1500:
            print("🟢 EXCELENTE: Sistema responde abaixo de 1.5s sob carga máxima.")
        elif p99 < 3000:
            print("🟡 ALERTA: Latência elevada. Risco de slippage em HFT, mas aceitável para 1h timeframe.")
        else:
            print("🔴 CRÍTICO: Gargalo de I/O ou API Rate Limit detectado. Necessário otimizar ThreadPool.")

if __name__ == "__main__":
    tester = StressTester()
    asyncio.run(tester.simulate_burst())
