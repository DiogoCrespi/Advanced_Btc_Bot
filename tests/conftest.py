# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def sample_ohlcv():
    """Gera um DataFrame OHLCV ficticio para testes com ruido para evitar NaNs no RSI."""
    dates = pd.date_range(start="2024-01-01", periods=200, freq="h")
    # Adicionando ruido para garantir que haja ganhos e perdas (necessario para RSI > 0 e < 100)
    close = np.linspace(100, 110, 200) + np.random.normal(0, 0.5, 200)
    df = pd.DataFrame({
        'open': close * 0.999,
        'high': close * 1.001,
        'low': close * 0.998,
        'close': close,
        'volume': np.random.randint(1, 10, 200)
    }, index=dates)
    return df

@pytest.fixture
def xaut_buy_signal_df():
    """Gera dados que devem disparar sinal de COMPRA em XAUTBTC (RSI baixo)."""
    dates = pd.date_range(start="2024-01-01", periods=200, freq="h")
    # Preco estavel e depois caindo forte para derrubar o RSI e BB
    close = np.concatenate([
        np.linspace(0.05, 0.05, 100) + np.random.normal(0, 0.0001, 100), 
        np.linspace(0.05, 0.01, 100)
    ])
    df = pd.DataFrame({
        'open': close, 'high': close*1.001, 'low': close*0.999, 'close': close, 'volume': 10
    }, index=dates)
    return df

@pytest.fixture
def xaut_sell_signal_df():
    """Gera dados que devem disparar sinal de VENDA em XAUTBTC (RSI alto)."""
    dates = pd.date_range(start="2024-01-01", periods=200, freq="h")
    # Preco estavel e depois subindo forte para elevar o RSI e BB
    close = np.concatenate([
        np.linspace(0.02, 0.02, 100) + np.random.normal(0, 0.0001, 100), 
        np.linspace(0.02, 0.08, 100)
    ])
    df = pd.DataFrame({
        'open': close, 'high': close*1.001, 'low': close*0.999, 'close': close, 'volume': 10
    }, index=dates)
    return df
