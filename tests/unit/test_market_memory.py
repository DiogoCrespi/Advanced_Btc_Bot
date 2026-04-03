# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
from logic.market_memory import MarketMemory

def test_market_memory_record_and_query():
    memory = MarketMemory()
    if not memory.driver:
        pytest.skip("Neo4j not available")
        
    # 1. Record a specific context
    sent = 0.88
    risk = 0.12
    action = "APPROVE_TEST"
    memory.record_context_and_decision(sent, risk, action)
    
    # 2. Record an outcome for it
    memory.record_outcome(0.05) # 5% profit
    
    # 3. Query similar context
    conviction = memory.get_historical_conviction(0.85, 0.15, tolerance=0.1)
    
    # Conviction should be > 0.5 because PnL was +5%
    assert conviction > 0.5
    print(f"Verified conviction: {conviction}")
    
    memory.close()
