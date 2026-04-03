# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import pandas as pd
import numpy as np
import sys
import os

# Adiciona o diretorio 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))

from usdt_brl_logic import UsdtBrlLogic

def test_usdt_features():
    logic = UsdtBrlLogic()
    # Criar dados simples
    dates = pd.date_range(start="2024-01-01", periods=60, freq="h")
    df = pd.DataFrame({'close': np.linspace(5.0, 5.5, 60)}, index=dates)
    
    df_feat = logic.compute_features(df)
    assert 'rsi' in df_feat.columns
    assert 'bb_pct' in df_feat.columns
    assert not df_feat.isnull().values.any()

def test_usdt_buy_signal():
    logic = UsdtBrlLogic()
    # Dados para sobre-venda (RSI < 35)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="h")
    # Preco caindo para forcar RSI baixo
    close = np.linspace(5.5, 4.8, 100) 
    df = pd.DataFrame({'close': close}, index=dates)
    df_feat = logic.compute_features(df)
    
    signal, conf, reason = logic.get_signal(df_feat, macro_risk=0.1)
    assert signal == 1
    assert "Discount" in reason

def test_usdt_safe_harbor_signal():
    logic = UsdtBrlLogic()
    dates = pd.date_range(start="2024-01-01", periods=100, freq="h")
    df = pd.DataFrame({'close': [5.0]*100}, index=dates)
    df_feat = logic.compute_features(df)
    
    # Risco macro alto deve forcar compra mesmo sem sinal tecnico
    signal, conf, reason = logic.get_signal(df_feat, macro_risk=0.9)
    assert signal == 1
    assert "Safe Harbor" in reason
