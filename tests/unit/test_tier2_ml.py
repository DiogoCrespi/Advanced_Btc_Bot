# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import pandas as pd
import numpy as np
import sys
import os

# Adiciona o diretorio 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from logic.ml_brain import MLBrain

@pytest.fixture
def mock_ml_data():
    """Gera dados para treinar o MLBrain."""
    # Aumentando para 1000 periodos e garantindo que os nomes das colunas coincidam com o aplicado no DataEngine
    dates = pd.date_range(start="2024-01-01", periods=1000, freq="h")
    # Simula um mercado com tendencia para o modelo aprender algo
    # Aumentando o desvio padrao consideravelmente para garantir volatidade e ativacao de diversidade de labels (Stop Loss / Take Profit)
    close = np.linspace(50000, 60000, 1000) + np.random.normal(0, 1500, 1000)
    df = pd.DataFrame({
        'open': close * 0.999,
        'high': close * 1.05,
        'low': close * 0.95,
        'close': close,
        'volume': np.random.uniform(10, 100, 1000),
        'SMA_50': pd.Series(close).rolling(50).mean().values,
        'EMA_21': pd.Series(close).ewm(span=21).mean().values,
        'RSI_14': np.random.uniform(30, 70, 1000),
        'Log_Returns': np.log(pd.Series(close)/pd.Series(close).shift(1)).fillna(0).values,
        'sweep_high': [0]*1000,
        'sweep_low': [0]*1000,
        'cvd_div': [0]*1000
    }, index=dates)
    return df.bfill().dropna()

def test_ml_prepare_features(mock_ml_data):
    brain = MLBrain()
    df_feat = brain.prepare_features(mock_ml_data)
    
    # Verifica se as colunas 'feat_' foram criadas
    feat_cols = [c for c in df_feat.columns if c.startswith('feat_')]
    assert len(feat_cols) > 0
    assert not df_feat[feat_cols].isnull().values.any()

def test_ml_train_predict(mock_ml_data):
    brain = MLBrain()
    # Treino rapido (full mode para simplificar o teste)
    brain.train(mock_ml_data, train_full=True)
    assert brain.is_trained == True
    
    # Testa predicao
    df_feat = brain.prepare_features(mock_ml_data)
    feat_cols = [c for c in df_feat.columns if c.startswith('feat_')]
    last_row = df_feat[feat_cols].values[-1]
    
    signal, prob, reason, rel = brain.predict_signal(last_row)
    assert signal in [-1, 0, 1]
    assert 0 <= prob <= 1.0
    assert isinstance(reason, str)
    assert 0 <= rel <= 1.0

def test_ml_brain_nan_inf_handling():
    """TESTE DE REJEICAO: Features corrompidas (NaN/Inf) devem retornar sinal neutro (0)."""
    brain = MLBrain()
    brain.is_trained = True # Mock as trained
    
    # Simula o estado das feature_cols apos um treino real
    dummy_features = ['feat_1', 'feat_2', 'feat_3']
    brain.feature_cols = dummy_features
    
    # Caso 1: NaN em uma feature
    nan_row = np.array([0.5, np.nan, 0.2])
    signal, prob, reason, rel = brain.predict_signal(nan_row)
    assert signal == 0
    assert "NaN ou Inf" in reason
    
    # Caso 2: Inf em uma feature
    inf_row = np.array([0.5, np.inf, 0.2])
    signal, prob, reason, rel = brain.predict_signal(inf_row)
    assert signal == 0
    assert "NaN ou Inf" in reason
