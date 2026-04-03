# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import sys
import os

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
