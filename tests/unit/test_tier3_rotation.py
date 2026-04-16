# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import sys
import os
import pandas as pd
import numpy as np

# Adiciona o diretorio 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data')))

from xaut_logic import XAUTAnalyzer

def test_xaut_analyzer_features(sample_ohlcv):
    analyzer = XAUTAnalyzer()
    df_feat = analyzer.compute_ratio_features(sample_ohlcv)
    
    assert 'ratio_rsi' in df_feat.columns
    assert 'bb_pct' in df_feat.columns
    assert not df_feat.isnull().values.any()
    assert len(df_feat) > 0

def test_compute_ratio_features_logic():
    """Testa a logica matematica das features calculadas por compute_ratio_features."""
    analyzer = XAUTAnalyzer()
    dates = pd.date_range(start="2024-01-01", periods=100, freq="h")
    # Semente fixa para previsibilidade no teste
    np.random.seed(42)
    # Array com tendencia e ruido para ter variancia, ganhos e perdas (evita NaNs no RSI e Bollinger Bands)
    close = np.linspace(100, 200, 100) + np.random.normal(0, 1.0, 100)
    df = pd.DataFrame({
        'open': close,
        'high': close + 1,
        'low': close - 1,
        'close': close,
        'volume': 10
    }, index=dates)

    df_feat = analyzer.compute_ratio_features(df)

    # max window e 50 periodos (ratio_sma50). Como usamos diff(5) na SMA20,
    # nao adiciona NaNs alem do window 50. Porem RSI e slope etc podem adicionar.
    # Pela natureza dos dados, len deve ser ao redor de 50.
    assert len(df_feat) > 0

    # Verifica ultimos valores das medias
    last_close_20 = close[-20:]
    last_close_50 = close[-50:]

    assert df_feat['ratio_sma20'].iloc[-1] == pytest.approx(np.mean(last_close_20))
    assert df_feat['ratio_sma50'].iloc[-1] == pytest.approx(np.mean(last_close_50))

    # Verifica Bollinger Bands
    std20 = np.std(last_close_20, ddof=1)
    expected_upper = np.mean(last_close_20) + 2 * std20
    expected_lower = np.mean(last_close_20) - 2 * std20

    assert df_feat['bb_upper'].iloc[-1] == pytest.approx(expected_upper)
    assert df_feat['bb_lower'].iloc[-1] == pytest.approx(expected_lower)

def test_xaut_buy_signal(xaut_buy_signal_df):
    analyzer = XAUTAnalyzer()
    df_feat = analyzer.compute_ratio_features(xaut_buy_signal_df)
    assert len(df_feat) > 0
    signal, confidence, reason, _ = analyzer.get_signal(df_feat)
    
    # E aceitavel sinal 0 se a confianca for baixa, mas o motivo deve indicar a direcao ou o filtro
    assert signal in [0, 1]
    if signal == 1:
        assert confidence >= analyzer.MIN_CONFIDENCE
    assert "XAUT" in reason or "Neutro" in reason

def test_xaut_sell_signal(xaut_sell_signal_df):
    analyzer = XAUTAnalyzer()
    df_feat = analyzer.compute_ratio_features(xaut_sell_signal_df)
    assert len(df_feat) > 0
    signal, confidence, reason, _ = analyzer.get_signal(df_feat)
    
    assert signal in [0, -1]
    if signal == -1:
        assert confidence >= analyzer.MIN_CONFIDENCE
    assert "XAUT" in reason or "Neutro" in reason

def test_xaut_dca_rejection():
    """TESTE DE REJEICAO: Nao deve permitir DCA se o preco estiver muito proximo da entrada anterior."""
    analyzer = XAUTAnalyzer()
    existing_positions = [
        {'id': 1, 'ratio_entry': 0.05, 'xaut_qty': 0.01}
    ]
    
    # Caso 1: Preco muito proximo (0.5% de distancia, limite e 1.5%)
    current_ratio = 0.0501 
    allowed = analyzer.is_dca_allowed(existing_positions, current_ratio, min_distance_pct=0.015)
    assert allowed == False
    
    # Caso 2: Preco longe o suficiente (2% de distancia)
    current_ratio = 0.0515
    allowed = analyzer.is_dca_allowed(existing_positions, current_ratio, min_distance_pct=0.015)
    assert allowed == True

def test_xaut_calc_pnl():
    """Testa o calculo de PnL em BTC e percentual."""
    analyzer = XAUTAnalyzer()

    # Caso 1: Lucro (PnL positivo)
    # Entrada: 10 XAUT a 0.05 BTC/XAUT -> custo_btc = 0.5
    # Atual: 0.06 BTC/XAUT -> valor_atual = 0.6
    # PnL BTC = 0.6 - 0.5 = 0.1
    # PnL % = 0.1 / 0.5 = 0.2 (20%)
    pos_profit = {'xaut_qty': 10.0, 'cost_btc': 0.5}
    current_ratio_profit = 0.06

    pnl_btc = analyzer.calc_pnl_btc(pos_profit, current_ratio_profit)
    pnl_pct = analyzer.calc_pnl_pct(pos_profit, current_ratio_profit)

    assert pnl_btc == pytest.approx(0.1)
    assert pnl_pct == pytest.approx(0.2)

    # Caso 2: Prejuizo (PnL negativo)
    # Entrada: 10 XAUT a 0.05 BTC/XAUT -> custo_btc = 0.5
    # Atual: 0.04 BTC/XAUT -> valor_atual = 0.4
    # PnL BTC = 0.4 - 0.5 = -0.1
    # PnL % = -0.1 / 0.5 = -0.2 (-20%)
    pos_loss = {'xaut_qty': 10.0, 'cost_btc': 0.5}
    current_ratio_loss = 0.04

    pnl_btc = analyzer.calc_pnl_btc(pos_loss, current_ratio_loss)
    pnl_pct = analyzer.calc_pnl_pct(pos_loss, current_ratio_loss)

    assert pnl_btc == pytest.approx(-0.1)
    assert pnl_pct == pytest.approx(-0.2)

    # Caso 3: Zero PnL
    pos_zero = {'xaut_qty': 10.0, 'cost_btc': 0.5}
    current_ratio_zero = 0.05

    assert analyzer.calc_pnl_btc(pos_zero, current_ratio_zero) == pytest.approx(0.0)
    assert analyzer.calc_pnl_pct(pos_zero, current_ratio_zero) == pytest.approx(0.0)

    # Caso 4: Custo BTC zero (edge case)
    pos_zero_cost = {'xaut_qty': 10.0, 'cost_btc': 0.0}
    current_ratio = 0.05

    assert analyzer.calc_pnl_btc(pos_zero_cost, current_ratio) == pytest.approx(0.5)
    assert analyzer.calc_pnl_pct(pos_zero_cost, current_ratio) == 0.0
