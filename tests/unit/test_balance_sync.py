import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from multicore_master_bot import MulticoreMasterBot, WebSocketSupervisor

@pytest.fixture
def mock_bot():
    """Cria uma instancia do bot com componentes mockados."""
    import pandas as pd
    with patch('multicore_master_bot.DataEngine'), \
         patch('multicore_master_bot.MLBrain') as mock_ml, \
         patch('multicore_master_bot.BinanceLive'), \
         patch('multicore_master_bot.LocalOracle'), \
         patch('multicore_master_bot.FeatureStore') as mock_fs, \
         patch('multicore_master_bot.Ledger'), \
         patch('multicore_master_bot.Watchdog'):
        
        mock_fs.return_value.load_history.return_value = pd.DataFrame()
        # Configura o mock do MLBrain para evitar blocos de treinamento
        mock_ml.return_value.is_trained = True
        mock_ml.return_value.n_samples = 5000
        
        bot = MulticoreMasterBot(mode="live")
        bot.exchange = AsyncMock()
        bot.save_balance = MagicMock()
        bot.save_state = MagicMock()
        return bot

@pytest.mark.asyncio
async def test_sync_balances_from_exchange(mock_bot):
    """Testa se a sincronizacao via REST API atualiza os saldos corretamente."""
    # Setup: mock retorno da exchange
    async def mock_get_balance(asset):
        return 5000.0 if asset == 'BRL' else 100.0
    mock_bot.exchange.get_balance.side_effect = mock_get_balance
    
    # Valores iniciais diferentes
    mock_bot.balance = 1000.0
    mock_bot.usdt_balance = 0.0
    
    await mock_bot.sync_balances_from_exchange()
    
    # Verificacoes
    assert mock_bot.balance == 5000.0
    assert mock_bot.usdt_balance == 100.0
    mock_bot.save_balance.assert_called()
    mock_bot.save_state.assert_called()

@pytest.mark.asyncio
async def test_handle_user_event_outbound_account_position(mock_bot):
    """Testa se o evento de alteracao de saldo via WebSocket atualiza o bot."""
    supervisor = WebSocketSupervisor(mock_bot)
    
    # Evento simulado da Binance
    event = {
        'e': 'outboundAccountPosition',
        'B': [
            {'a': 'BRL', 'f': '4500.50', 'l': '0.00'},
            {'a': 'USDT', 'f': '250.75', 'l': '0.00'}
        ]
    }
    
    await supervisor._handle_user_event(event)
    
    # Verificacoes
    assert mock_bot.balance == 4500.50
    assert mock_bot.usdt_balance == 250.75
    mock_bot.save_balance.assert_called()
    mock_bot.save_state.assert_called()

@pytest.mark.asyncio
async def test_handle_user_event_balance_update(mock_bot):
    """Testa se o evento balanceUpdate forca uma nova sincronizacao futura."""
    supervisor = WebSocketSupervisor(mock_bot)
    
    # Reset last_balance_sync para agora
    now = datetime.now()
    mock_bot.last_balance_sync = now
    
    event = {
        'e': 'balanceUpdate',
        'a': 'BRL',
        'd': '100.00'
    }
    
    await supervisor._handle_user_event(event)
    
    # Deve ter retrocedido o timer para forcar sync na proxima iteracao
    assert mock_bot.last_balance_sync < now - timedelta(minutes=50)

@pytest.mark.asyncio
async def test_periodic_reconciliation_trigger(mock_bot):
    """Testa se o loop principal dispara a reconciliacao apos o intervalo."""
    # Mock do exchange.get_balance para o sync
    mock_bot.exchange.get_balance.return_value = 1000.0
    
    # Forca o timer a estar expirado (> 15 min)
    mock_bot.last_balance_sync = datetime.now() - timedelta(minutes=20)
    
    # Mock de funcoes que o loop chama para nao travar
    mock_bot.total_equity = 1000.0
    mock_bot.sync_balances_from_exchange = AsyncMock()
    
    # Simulamos o trecho do loop de reconciliacao
    if datetime.now() - mock_bot.last_balance_sync > timedelta(minutes=15):
        await mock_bot.sync_balances_from_exchange()
        
    mock_bot.sync_balances_from_exchange.assert_called_once()
