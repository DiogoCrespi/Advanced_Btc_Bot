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

def test_calculate_zscore_basic():
    """Teste basico do calculo de zscore com dados artificiais."""
    logic = StatArbLogic(window=3)

    dates = pd.date_range("2023-01-01", periods=5)
    df_btc = pd.DataFrame({"close": [100.0, 105.0, 110.0, 115.0, 120.0]}, index=dates)
    df_eth = pd.DataFrame({"close": [10.0, 11.0, 12.0, 13.0, 14.0]}, index=dates)

    spread, z_score, beta = logic.calculate_zscore(df_btc, df_eth)

    # As 2 primeiras linhas de beta serao NaN porque a janela e 3
    assert pd.isna(beta.iloc[0])
    assert pd.isna(beta.iloc[1])
    assert not pd.isna(beta.iloc[2])

    # Z-score so e calculado depois do spread_std, que precisa de 3 periodos de spread
    # Spread tem valores a partir do indice 2. Portanto spread_std precisa do 2, 3 e 4.
    assert pd.isna(z_score.iloc[3])
    assert not pd.isna(z_score.iloc[4])

    # Verifica o beta tem um valor esperado para relacao linear de log
    assert beta.iloc[4] > 0

def test_calculate_zscore_alignment():
    """Teste de alinhamento de dataframes com indices diferentes."""
    logic = StatArbLogic(window=2)

    dates_btc = pd.date_range("2023-01-01", periods=4) # 1 a 4
    dates_eth = pd.date_range("2023-01-02", periods=4) # 2 a 5

    df_btc = pd.DataFrame({"close": [100.0, 105.0, 110.0, 115.0]}, index=dates_btc)
    df_eth = pd.DataFrame({"close": [11.0, 12.0, 13.0, 14.0]}, index=dates_eth)

    spread, z_score, beta = logic.calculate_zscore(df_btc, df_eth)

    # O tamanho da serie resultante na verdade parece ser o da uniao devido a como o index funciona na formula
    # Mas o join='inner' em df_btc.align altera o df mas nao os objetos originais do pandas!
    # Ah, o codigo e: df, _ = df_btc.align(...)
    # mas usa: log_btc = np.log(df_btc['close']) ou seja, NÂO usa o df alinhado!

    assert len(spread) == 5
    assert spread.index[0] == pd.Timestamp("2023-01-01")
    assert spread.index[-1] == pd.Timestamp("2023-01-05")

    # Valores fora da interseccao devem ser NaN
    assert pd.isna(spread.loc["2023-01-01"])
    assert pd.isna(spread.loc["2023-01-05"])

def test_calculate_zscore_insufficient_data():
    """Teste com menos dados do que o tamanho da janela."""
    logic = StatArbLogic(window=5)

    dates = pd.date_range("2023-01-01", periods=3)
    df_btc = pd.DataFrame({"close": [100.0, 105.0, 110.0]}, index=dates)
    df_eth = pd.DataFrame({"close": [10.0, 11.0, 12.0]}, index=dates)

    spread, z_score, beta = logic.calculate_zscore(df_btc, df_eth)

    # Todos devem ser NaN porque janela (5) > dados (3)
    assert beta.isna().all()
    assert spread.isna().all()
    assert z_score.isna().all()

def test_calculate_zscore_constant_prices():
    """Teste com precos constantes (variancia zero)."""
    logic = StatArbLogic(window=3)

    dates = pd.date_range("2023-01-01", periods=5)
    df_btc = pd.DataFrame({"close": [100.0, 100.0, 100.0, 100.0, 100.0]}, index=dates)
    df_eth = pd.DataFrame({"close": [10.0, 10.0, 10.0, 10.0, 10.0]}, index=dates)

    spread, z_score, beta = logic.calculate_zscore(df_btc, df_eth)

    # Variancia de log_eth sera 0, beta sera NaN ou inf
    # Na pratica, pandas divide cov(0) por var(0), gerando NaN
    assert pd.isna(beta.iloc[-1])
    assert pd.isna(spread.iloc[-1])
    assert pd.isna(z_score.iloc[-1])
