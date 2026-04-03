# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import pandas as pd
import numpy as np
import sys
import os

# Adiciona o diretorio 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))

from gap_logic import GapLogic

def test_real_opportunity_breakaway():
    """
    TESTE DE OPORTUNIDADE: Gap de rompimento com volume alto e confluencia.
    Deve ser classificado como oportunidade real (conviction >= 0.7).
    """
    logic = GapLogic()
    
    # 30 periodos de consolidacao
    df = pd.DataFrame({
        'open':   [100.0]*30,
        'close':  [100.0]*30,
        'high':   [101.0]*30,
        'low':    [99.0]*30,
        'volume': [100.0]*30,
        'SMA_50': [100.0]*30 # SMA_50 estavel
    })
    # Injecao de um Breakaway Gap no indice 30
    new_row = pd.DataFrame({
        'open': [105.0],  # Gap de 5%
        'close': [106.0],
        'high': [107.0],
        'low': [104.0],
        'volume': [500.0], # Volume 5x maior
        'SMA_50': [100.5], # Slope positivo
        'cvd_div': [1]     # Divergencia CVD positiva (Buyer absorption)
    })
    df = pd.concat([df, new_row]).reset_index(drop=True)
    
    conviction, is_opp, classification = logic.evaluate_opportunity(df, 30)
    
    assert classification == "Breakaway"
    assert is_opp == True
    assert conviction >= 0.7

def test_exhaustion_risk():
    """
    TESTE DE RISCO: Gap no final de uma tendencia esticada.
    Deve ser classificado como Exaustao e NAO ser uma oportunidade real.
    """
    logic = GapLogic()
    # Tendencia de alta esticada (>5% em 10 candles)
    prices = np.linspace(100, 120, 31)
    df = pd.DataFrame({
        'open':   prices,
        'close':  prices,
        'high':   prices * 1.01,
        'low':    prices * 0.99,
        'volume': [100.0]*31,
        'SMA_50': prices
    })
    # Gap Final de Exaustao
    new_row = pd.DataFrame({
        'open': [125.0],
        'close': [126.0],
        'high': [128.0],
        'low': [124.0],
        'volume': [600.0], # Volume altissimo
        'SMA_50': [121.0],
        'cvd_div': [0]
    })
    df = pd.concat([df, new_row]).reset_index(drop=True)
    
    conviction, is_opp, classification = logic.evaluate_opportunity(df, 31)
    
    assert classification == "Exhaustion"
    assert is_opp == False
    assert conviction < 0.5 # Penalizacao por exaustao deve baixar a conviccao

def test_common_gap_no_conviction():
    """
    TESTE NEUTRO: Gap comum sem volume ou contexto.
    Deve ter baixa conviccao e nao ser uma oportunidade.
    """
    logic = GapLogic()
    df = pd.DataFrame({
        'open':   [100.0]*30,
        'close':  [100.0]*30,
        'high':   [101.0]*30,
        'low':    [99.0]*30,
        'volume': [100.0]*30
    })
    # Gap de 0.6% com volume normal
    new_row = pd.DataFrame({
        'open': [100.6],
        'close': [100.8],
        'high': [101.0],
        'low': [100.5],
        'volume': [105.0]
    })
    df = pd.concat([df, new_row]).reset_index(drop=True)
    
    conviction, is_opp, classification = logic.evaluate_opportunity(df, 30)
    
    assert classification == "Common"
    assert is_opp == False
    assert conviction < 0.5
