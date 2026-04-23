import asyncio
import os
import logging
from data.data_engine import DataEngine
from logic.coingecko_client import CoinGeckoClient
from logic.local_oracle import LocalOracle
from dotenv import load_dotenv

# Configurar logging para ver erros do Oracle
logging.basicConfig(level=logging.INFO)

async def diag():
    load_dotenv()
    engine = DataEngine()
    cg = CoinGeckoClient()
    
    # Mocking dependencies for Oracle
    class MockMemory:
        def __init__(self): self.db = None
        def get_recent_failures(self, limit=3): return []
    
    shared_state = {"sentiment": "Neutral", "confidence": 0.5, "multiplier": 1.0}
    oracle = LocalOracle(memory_module=MockMemory(), shared_state=shared_state)
    
    print("--- DIAGNOSTICO ---")
    df = engine.fetch_binance_klines("BTCBRL", limit=10)
    print(f"BTCBRL Close: {df['close'].iloc[-1] if not df.empty else 'N/A'}")
    
    dom = cg.get_btc_dominance()
    print(f"BTC Dominance: {dom}")
    
    macro = engine.fetch_macro_data()
    print(f"Macro Data: {macro}")
    
    print("Testando Oracle (_evaluate_comite)...")
    await oracle._evaluate_comite()
    print(f"Oracle Result: {shared_state}")

if __name__ == '__main__':
    asyncio.run(diag())
