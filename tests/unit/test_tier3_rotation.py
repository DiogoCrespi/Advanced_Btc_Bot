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

def test_xaut_buy_signal(xaut_buy_signal_df):
    analyzer = XAUTAnalyzer()
    df_feat = analyzer.compute_ratio_features(xaut_buy_signal_df)
    assert len(df_feat) > 0
    signal, confidence, reason = analyzer.get_signal(df_feat)
    
    # E aceitavel sinal 0 se a confianca for baixa, mas o motivo deve indicar a direcao ou o filtro
    assert signal in [0, 1]
    if signal == 1:
        assert confidence >= analyzer.MIN_CONFIDENCE
    assert "XAUT" in reason or "Neutro" in reason

def test_xaut_sell_signal(xaut_sell_signal_df):
    analyzer = XAUTAnalyzer()
    df_feat = analyzer.compute_ratio_features(xaut_sell_signal_df)
    assert len(df_feat) > 0
    signal, confidence, reason = analyzer.get_signal(df_feat)
    
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

def test_xaut_get_signal_branches():
    """Testa exaustivamente todas as branches condicionais do metodo get_signal."""
    analyzer = XAUTAnalyzer()

    # Branch 1: Invalid input (None)
    sig, conf, reason = analyzer.get_signal(None)
    assert sig == 0
    assert conf == 0.0
    assert reason == "Dados insuficientes"

    # Branch 2: Invalid input (len < 2)
    df_empty = pd.DataFrame()
    sig, conf, reason = analyzer.get_signal(df_empty)
    assert sig == 0
    assert conf == 0.0
    assert reason == "Dados insuficientes"

    # Branch 3: Corrupted data (NaN)
    df_nan = pd.DataFrame({'ratio_rsi': [np.nan, np.nan], 'bb_pct': [0.5, 0.5], 'ratio_slope': [0.0, 0.0]})
    sig, conf, reason = analyzer.get_signal(df_nan)
    assert sig == 0
    assert conf == 0.0
    assert reason == "Features invalidas (NaN/Inf)"

    # Helper function to create mock df
    def make_df(rsi, bb, slope=0.0):
        return pd.DataFrame({
            'ratio_rsi': [50.0, rsi],
            'bb_pct': [0.5, bb],
            'ratio_slope': [0.0, slope]
        })

    # Branch 4: Strong Buy Signal (RSI < RSI_BUY_STRONG, BB < BB_BUY_ZONE)
    # analyzer.RSI_BUY_STRONG = 32, analyzer.BB_BUY_ZONE = 0.15
    df_strong_buy = make_df(30, 0.1, 0.0)
    sig, conf, reason = analyzer.get_signal(df_strong_buy)
    assert sig == 1
    assert conf >= 0.55
    assert "XAUT Barato" in reason

    # Branch 5: Mild Buy Signal (RSI < RSI_BUY_MILD, slope > 0.0002)
    # analyzer.RSI_BUY_MILD = 42
    df_mild_buy = make_df(40, 0.5, 0.0003)
    sig, conf, reason = analyzer.get_signal(df_mild_buy)
    assert sig == 1
    assert conf >= 0.53
    assert "Momentum Ouro Crescente" in reason

    # Branch 6: Reversion Bottom Buy (BB < BB_BUY_ZONE, slope > 0)
    df_rev_buy = make_df(50, 0.1, 0.0001)
    sig, conf, reason = analyzer.get_signal(df_rev_buy)
    # The initial signal assigned is 1, confidence 0.52.
    # MIN_CONFIDENCE check: 0.52 < 0.55 -> signal becomes 0.
    assert sig == 0 # due to min_confidence filter!
    assert conf == 0.52
    assert "Mean Reversion Fundo" in reason

    # Branch 7: Strong Sell Signal (RSI > RSI_SELL_STRONG, BB > BB_SELL_ZONE)
    # analyzer.RSI_SELL_STRONG = 68, analyzer.BB_SELL_ZONE = 0.85
    df_strong_sell = make_df(70, 0.9, 0.0)
    sig, conf, reason = analyzer.get_signal(df_strong_sell)
    assert sig == -1
    assert conf >= 0.55
    assert "XAUT Caro" in reason

    # Branch 8: Mild Sell Signal (RSI > RSI_SELL_MILD, BB > BB_SELL_ZONE)
    # analyzer.RSI_SELL_MILD = 58
    df_mild_sell = make_df(60, 0.9, 0.0)
    sig, conf, reason = analyzer.get_signal(df_mild_sell)
    # Confidence 0.52 < 0.55 -> signal becomes 0
    assert sig == 0
    assert conf == 0.52
    assert "Sobrecompra Ratio" in reason

    # Branch 9: Neutral
    df_neutral = make_df(50, 0.5, 0.0)
    sig, conf, reason = analyzer.get_signal(df_neutral)
    assert sig == 0
    assert conf == 0.0
    assert reason == "Ratio Neutro"
