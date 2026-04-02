import pytest
import pandas as pd
import numpy as np
import sys
import os

# Adiciona o diretório 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from logic.gap_logic import GapLogic

@pytest.fixture
def fvg_data():
    """Gera dados para testar Fair Value Gap (FVG)."""
    dates = pd.date_range(start="2024-01-01", periods=10, freq="h")
    df = pd.DataFrame({
        'open':  [45, 51, 61, 65, 66, 67, 68, 69, 70, 71],
        'high':  [50, 60, 70, 72, 73, 74, 75, 76, 77, 78],
        'low':   [40, 50, 60, 63, 64, 65, 66, 67, 68, 69],
        'close': [48, 59, 69, 71, 72, 73, 74, 75, 76, 77],
        'volume':[10, 50, 10, 10, 10, 10, 10, 10, 10, 10]
    }, index=dates)
    return df

def test_detect_fvg_bullish(fvg_data):
    logic = GapLogic()
    df_feat = logic.detect_fvg(fvg_data)
    assert df_feat['fvg_bullish'].iloc[2] == 10.0
    assert df_feat['fvg_target'].iloc[2] == 55.0

def test_detect_fvg_bearish():
    logic = GapLogic()
    dates = pd.date_range(start="2024-01-01", periods=3, freq="h")
    df = pd.DataFrame({
        'high':  [110, 95, 90],
        'low':   [100, 85, 80],
        'open':  [105, 95, 85],
        'close': [102, 90, 82],
        'volume':[10, 50, 10]
    }, index=dates)
    df_feat = logic.detect_fvg(df)
    assert df_feat['fvg_bearish'].iloc[2] == 10.0
    assert df_feat['fvg_target'].iloc[2] == 95.0

def test_classify_breakaway():
    logic = GapLogic()
    # Consolidação lateral lateral (trend < 1%)
    df = pd.DataFrame({
        'open':   [100.0]*30,
        'close':  [100.0]*30,
        'high':   [101.0]*30,
        'low':    [99.0]*30,
        'volume': [100.0]*30
    })
    # Gap de 10%
    new_row = pd.DataFrame({
        'open': [110.0],
        'close': [111.0],
        'high': [112.0],
        'low': [109.0],
        'volume': [500.0]
    })
    df = pd.concat([df, new_row]).reset_index(drop=True)
    
    gap_type = logic.classify_gap(df, 30)
    assert gap_type == "Breakaway"

def test_classify_exhaustion():
    logic = GapLogic()
    # Tendência de alta EXTREMAMENTE esticada
    # Usando rampa agressiva para bater abs(trend) > 0.05 nos últimos 10 candles
    prices = np.linspace(100, 200, 31) # Dobro do preço
    df = pd.DataFrame({
        'open':   prices,
        'close':  prices,
        'high':   prices * 1.01,
        'low':    prices * 0.99,
        'volume': [100.0]*31
    })
    # Gap de Exhaustion
    new_row = pd.DataFrame({
        'open': [210.0],
        'close': [212.0],
        'high': [215.0],
        'low': [209.0],
        'volume': [500.0]
    })
    df = pd.concat([df, new_row]).reset_index(drop=True)
    
    # Índice 31 é a nova linha
    gap_type = logic.classify_gap(df, 31)
    assert gap_type == "Exhaustion"

def test_gap_logic_insufficient_data():
    """TESTE DE REJEIÇÃO: Dados insuficientes não devem causar crash."""
    logic = GapLogic()
    # Caso 1: DataFrame com apenas 1 linha para FVG (Precisa de 3)
    df_short = pd.DataFrame({'high':[100], 'low':[90], 'close':[95], 'open':[92]})
    df_feat = logic.detect_fvg(df_short)
    # Deve lidar sem erro de índice (usando .shift(2) no numpy/pandas retorna NaN mas não crasha)
    assert df_feat['fvg_bullish'].isnull().all() or (df_feat['fvg_bullish'] == 0).all()
    
    # Caso 2: Classify gap com row_idx baixo (< 20)
    res = logic.classify_gap(df_short, 0)
    assert res == "None"
