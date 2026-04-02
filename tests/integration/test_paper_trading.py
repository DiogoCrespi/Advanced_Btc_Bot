import pytest
import os
import sys
import json
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from multicore_master_bot import MulticoreMasterBot

@pytest.fixture
def mock_bot():
    """Inicializa o bot com dependências mockadas para evitar chamadas de rede."""
    with patch('multicore_master_bot.DataEngine') as mock_engine, \
         patch('multicore_master_bot.MLBrain') as mock_brain, \
         patch('multicore_master_bot.Client') as mock_client:
        
        # Mock do DataEngine
        engine_inst = mock_engine.return_value
        dates = pd.date_range(start="2024-01-01", periods=100, freq="h")
        mock_df = pd.DataFrame({
            'open': [50000]*100, 'high': [51000]*100, 'low': [49000]*100, 'close': [50000]*100, 'volume': [10]*100
        }, index=dates)
        
        engine_inst.fetch_binance_klines.return_value = mock_df
        engine_inst.apply_indicators.return_value = mock_df
        engine_inst.fetch_usdt_brl_data.return_value = mock_df
        engine_inst.fetch_xaut_ratio.return_value = mock_df
        engine_inst.fetch_delivery_contracts.return_value = []
        
        # Mock do MLBrain
        brain_inst = mock_brain.return_value
        brain_inst.train.return_value = 0.85
        brain_inst.predict_signal.return_value = (0, 0.5, "Neutral")
        
        # Limpar arquivos de resultados de testes anteriores
        if not os.path.exists("results"): os.makedirs("results")
        
        bot = MulticoreMasterBot(live_mode=False)
        return bot

def test_paper_trading_initialization(mock_bot):
    """Verifica se o bot inicia com saldo padrão de R$ 1000 em modo simulação."""
    assert mock_bot.live_mode == False
    assert mock_bot.balance >= 1000.0
    assert mock_bot.usdt_balance == 0.0

def test_paper_trading_process_usdt(mock_bot):
    """Simula o processamento de USDT no modo Paper Trading."""
    # Forçamos um sinal de compra de USDT
    mock_bot.usdt_logic.get_signal = MagicMock(return_value=(1, 0.9, "Test Buy"))
    mock_bot.agent.assess_usdt_opportunity = MagicMock(return_value=("APPROVE", "Test Reason"))
    
    mock_bot._process_usdt("12:00:00")
    
    # Saldo BRL deve ter diminuído e saldo USDT aumentado
    assert mock_bot.balance < 1000.0
    assert mock_bot.usdt_balance > 0.0
    
    # Verifica se o log foi gerado
    assert os.path.exists("results/signals_log.txt")

def test_paper_trading_save_state(mock_bot):
    """Verifica se o estado é salvo corretamente em JSON."""
    mock_bot.balance = 1234.56
    mock_bot.save_state()
    
    # Aguarda um pouco o thread de log
    import time
    time.sleep(0.5)
    
    assert os.path.exists("results/bot_status.json")
    with open("results/bot_status.json", "r") as f:
        data = json.load(f)
        assert data['balance'] == 1234.56
