import pytest
import sys
import os
from datetime import datetime, timedelta

# Adiciona o diretório 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))

from basis_logic import BasisLogic

def test_basis_calculation():
    logic = BasisLogic(risk_free_rate_annual=0.10)
    spot_price = 350000.0  # BTCBRL
    fut_price = 360000.0   # BTCBRL_260626
    
    # Simula expiração em 1 ano
    expiry_date = datetime.now() + timedelta(days=365)
    
    yield_apr = logic.calculate_annualized_yield(spot_price, fut_price, expiry_date)
    
    # 360k / 350k = 1.0285...
    # (1.0285 - 1) / 1.0 (anos)
    assert yield_apr > 0.02
    assert yield_apr < 0.03

def test_best_contract():
    logic = BasisLogic()
    results = [
        {'symbol': 'CONT1', 'yield_apr': 0.05},
        {'symbol': 'CONT2', 'yield_apr': 0.08},
        {'symbol': 'CONT3', 'yield_apr': 0.03},
    ]
    best = logic.get_best_contract(results)
    assert best['symbol'] == 'CONT2'

def test_basis_zero_price_handling():
    """TESTE DE REJEIÇÃO: Preços zero não devem causar crash."""
    logic = BasisLogic()
    # Caso 1: Spot zero
    yield_apr = logic.calculate_annualized_yield(0, 360000, datetime.now() + timedelta(days=365))
    assert yield_apr == 0
    
    # Caso 2: Futuro zero
    yield_apr = logic.calculate_annualized_yield(350000, 0, datetime.now() + timedelta(days=365))
    assert yield_apr == 0
