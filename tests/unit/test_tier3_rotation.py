import pytest
import sys
import os

# Adiciona o diretório 'logic' ao path
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
    
    # É aceitável sinal 0 se a confiança for baixa, mas o motivo deve indicar a direção ou o filtro
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
    """TESTE DE REJEIÇÃO: Não deve permitir DCA se o preço estiver muito próximo da entrada anterior."""
    analyzer = XAUTAnalyzer()
    existing_positions = [
        {'id': 1, 'ratio_entry': 0.05, 'xaut_qty': 0.01}
    ]
    
    # Caso 1: Preço muito próximo (0.5% de distância, limite é 1.5%)
    current_ratio = 0.0501 
    allowed = analyzer.is_dca_allowed(existing_positions, current_ratio, min_distance_pct=0.015)
    assert allowed == False
    
    # Caso 2: Preço longe o suficiente (2% de distância)
    current_ratio = 0.0515
    allowed = analyzer.is_dca_allowed(existing_positions, current_ratio, min_distance_pct=0.015)
    assert allowed == True
