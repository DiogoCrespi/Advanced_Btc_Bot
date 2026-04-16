# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import os
import sys
import json
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

# Adiciona o diretorio raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from multicore_master_bot import MulticoreMasterBot

@pytest.fixture
def mock_bot():
    """Inicializa o bot com dependencias mockadas para evitar chamadas de rede."""
    with patch('multicore_master_bot.DataEngine') as mock_engine, \
         patch('multicore_master_bot.MLBrain') as mock_brain:
        
        # Mock do DataEngine
        engine_inst = mock_engine.return_value
        dates = pd.date_range(start="2024-01-01", periods=100, freq="h")
        mock_df = pd.DataFrame({
            'open': [50000]*100, 'high': [51000]*100, 'low': [49000]*100, 'close': [50000]*100, 'volume': [10]*100,
            'rsi': [50.0]*100, 'bb_pct': [0.5]*100, 'slope': [0.0]*100,
            'ratio_rsi': [50.0]*100, 'ratio_slope': [0.0]*100
        }, index=dates)
        
        engine_inst.fetch_binance_klines.return_value = mock_df
        engine_inst.apply_indicators.return_value = mock_df
        engine_inst.fetch_usdt_brl_data.return_value = mock_df
        engine_inst.fetch_xaut_ratio.return_value = mock_df
        engine_inst.fetch_delivery_contracts.return_value = []
        engine_inst.fetch_macro_data.return_value = {'dxy_change':0, 'sp500_change':0, 'gold_change':0}
        
        # Mock do MLBrain
        brain_inst = mock_brain.return_value
        brain_inst.train.return_value = 0.85
        brain_inst.predict_signal.return_value = (0, 0.5, "Neutral", 1.0)
        
        # Limpar arquivos de resultados de testes anteriores para garantir estado limpo
        if not os.path.exists("results"): os.makedirs("results")
        for f in ["results/balance_state.txt", "results/bot_status.json", "results/signals_log.txt"]:
            if os.path.exists(f): os.remove(f)
        
        bot = MulticoreMasterBot(mode="backtest")
        return bot

def test_paper_trading_initialization(mock_bot):
    """Verifica se o bot inicia com saldo padrao de R$ 1000 em modo simulacao."""
    assert mock_bot.mode == "backtest"
    assert mock_bot.balance >= 1000.0
    assert mock_bot.usdt_balance == 0.0

def test_paper_trading_process_usdt(mock_bot):
    """Simula o processamento de USDT no modo Paper Trading."""
    # Forcamos um sinal de compra de USDT (4-tuple)
    mock_bot.usdt_logic.get_signal = MagicMock(return_value=(1, 0.9, "Test Buy", {'rsi': 30}))
    mock_bot.agent.assess_usdt_opportunity = MagicMock(return_value=("APPROVE", "Test Reason"))
    
    # Passamos um float para macro_risk
    mock_bot._process_usdt(0.5)
    
    # Saldo BRL deve ter diminuido e saldo USDT aumentado
    assert mock_bot.balance < 1000.0
    assert mock_bot.usdt_balance > 0.0

def test_paper_trading_save_state(mock_bot):
    """Verifica se o estado e salvo corretamente em JSON."""
    mock_bot.balance = 1234.56
    mock_bot.save_state()
    
    # Aguarda um pouco o thread de log
    import time
    time.sleep(0.5)
    
    assert os.path.exists("results/bot_status.json")
    with open("results/bot_status.json", "r") as f:
        data = json.load(f)
        assert data['balance'] == 1234.56
