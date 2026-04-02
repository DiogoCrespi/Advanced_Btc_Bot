import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Adiciona o diretório 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))
from gap_logic import GapLogic

def test_cme_gap_simulation():
    """
    Simula um gap de fim de semana (CME Gap).
    Sexta-feira fecha em $60,000.
    Domingo abre em $62,000.
    """
    logic = GapLogic()
    
    # Criar 100 horas de dados
    dates = pd.date_range(start="2024-01-01", periods=100, freq="h")
    df = pd.DataFrame({
        'open':  [60000]*100,
        'high':  [60500]*100,
        'low':   [59500]*100,
        'close': [60000]*100,
        'volume':[100]*100
    }, index=dates)
    
    # Injetar o Gap em T=50
    df.loc[df.index[50], 'open'] = 65000 # Gap de 5k (8.3%)
    
    df_feat = logic.detect_cme_gaps(df)
    
    # Verifica o tamanho do gap no índice 50
    assert df_feat['gap_size'].iloc[50] > 0.08
    assert df_feat['gap_size'].iloc[50] < 0.09

def test_fvg_magnet_effect():
    """
    Verifica se a detecção de FVG gera um alvo (target) de liquidez coerente.
    Bullish FVG: O preço deve 'voltar' para preencher a lacuna.
    """
    logic = GapLogic()
    
    # 3 candles formando um Fair Value Gap de Alta
    # C1: H=100, C2: IMPULSE (L=100, H=120), C3: L=110
    # Gap: entre 100 e 110. Target: 105.
    df = pd.DataFrame({
        'high':  [100, 120, 120],
        'low':   [90, 100, 110],
        'close': [95, 115, 118],
        'open':  [92, 95, 115]
    })
    
    df_feat = logic.detect_fvg(df)
    
    # O gap deve ser detectado no candle 2 (C3)
    assert df_feat['fvg_bullish'].iloc[2] == 10.0 # 110 - 100
    assert df_feat['fvg_target'].iloc[2] == 105.0 # (100 + 110) / 2
