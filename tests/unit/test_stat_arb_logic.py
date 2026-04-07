# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import sys
import os
import pandas as pd
import numpy as np

# Adiciona o diretorio 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from logic.stat_arb_logic import StatArbLogic

def test_is_spread_profitable_z_stop():
    """Teste da condicao Z-Stop: Se o desvio for extremo, a cointegracao quebrou."""
    logic = StatArbLogic()
    # Z-score > 4.0 deve retornar False independente do profit margin
    assert logic.is_spread_profitable(z_score=4.1, spread_current=1.0, spread_mean=0.0) == False
    assert logic.is_spread_profitable(z_score=-4.1, spread_current=1.0, spread_mean=0.0) == False

def test_is_spread_profitable_edge_z_stop():
    """Teste da fronteira exata do Z-Stop (abs(z_score) == 4.0)."""
    logic = StatArbLogic()
    # Z-score == 4.0 deve avaliar a margem de lucro (0.05 > 0.002)
    assert logic.is_spread_profitable(z_score=4.0, spread_current=0.05, spread_mean=0.0) == True
    assert logic.is_spread_profitable(z_score=-4.0, spread_current=0.05, spread_mean=0.0) == True

def test_is_spread_profitable_profitable():
    """Teste de margem esperada maior que as taxas."""
    logic = StatArbLogic()
    # expected_profit_margin = abs(0.01 - 0.0) = 0.01 > 0.002
    assert logic.is_spread_profitable(z_score=2.0, spread_current=0.01, spread_mean=0.0) == True
    assert logic.is_spread_profitable(z_score=-2.0, spread_current=-0.01, spread_mean=0.0) == True

def test_is_spread_profitable_unprofitable():
    """Teste de margem esperada menor ou igual as taxas."""
    logic = StatArbLogic()
    # expected_profit_margin = abs(0.002 - 0.0) = 0.002 <= 0.002
    assert logic.is_spread_profitable(z_score=2.0, spread_current=0.002, spread_mean=0.0) == False
    # expected_profit_margin = abs(0.001 - 0.0) = 0.001 <= 0.002
    assert logic.is_spread_profitable(z_score=-2.0, spread_current=-0.001, spread_mean=0.0) == False

def test_is_spread_profitable_custom_fee():
    """Teste passando um valor de taxa customizado."""
    logic = StatArbLogic()
    # expected_profit_margin = abs(0.005 - 0.0) = 0.005 <= 0.01
    assert logic.is_spread_profitable(z_score=2.0, spread_current=0.005, spread_mean=0.0, fee_total=0.01) == False
    # expected_profit_margin = abs(0.015 - 0.0) = 0.015 > 0.01
    assert logic.is_spread_profitable(z_score=2.0, spread_current=0.015, spread_mean=0.0, fee_total=0.01) == True

def test_get_signal_nan():
    """Teste do get_signal para valor NaN."""
    logic = StatArbLogic()
    assert logic.get_signal(np.nan) is None

def test_get_signal_short():
    """Teste do get_signal para sinal SHORT (z_score > threshold)."""
    logic = StatArbLogic(z_threshold=2.0)
    assert logic.get_signal(2.1) == -1

def test_get_signal_long():
    """Teste do get_signal para sinal LONG (z_score < -threshold)."""
    logic = StatArbLogic(z_threshold=2.0)
    assert logic.get_signal(-2.1) == 1

def test_get_signal_mean_reversion():
    """Teste do get_signal para reversao a media (abs(z_score) < 0.1)."""
    logic = StatArbLogic(z_threshold=2.0)
    assert logic.get_signal(0.05) == 0
    assert logic.get_signal(-0.05) == 0

def test_get_signal_no_action():
    """Teste do get_signal para nenhuma acao (0.1 <= abs(z_score) <= threshold)."""
    logic = StatArbLogic(z_threshold=2.0)
    assert logic.get_signal(1.5) is None
    assert logic.get_signal(-1.5) is None
    # Boundary: exact threshold
    assert logic.get_signal(2.0) is None
    assert logic.get_signal(-2.0) is None
    # Boundary: exact 0.1
    assert logic.get_signal(0.1) is None
    assert logic.get_signal(-0.1) is None
