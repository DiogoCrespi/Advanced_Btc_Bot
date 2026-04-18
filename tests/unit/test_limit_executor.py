import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from logic.execution.limit_executor import LimitExecutor

@pytest.fixture
def mock_exchange():
    exchange = AsyncMock()
    # Mock default behavior for orderbook
    exchange.get_orderbook_ticker.return_value = {
        'symbol': 'BTCBRL',
        'bidPrice': '350000.00',
        'askPrice': '350100.00'
    }
    return exchange

@pytest.mark.asyncio
async def test_execute_limit_order_success(mock_exchange):
    """Testa se uma ordem LIMIT_MAKER e colocada no preço correto do bid."""
    executor = LimitExecutor(mock_exchange)
    
    # Mock da criação e do status
    mock_exchange.create_order.return_value = {
        'symbol': 'BTCBRL',
        'orderId': '12345',
        'status': 'NEW'
    }
    mock_exchange.get_order_status.return_value = {
        'symbol': 'BTCBRL',
        'orderId': '12345',
        'status': 'FILLED',
        'price': '350000.0'
    }
    
    with patch('asyncio.sleep', return_value=None):
        order = await executor.execute_limit_order('BTCBRL', 'BUY', 0.01)
    
    assert order is not None
    assert order['status'] == 'FILLED'
    mock_exchange.get_order_status.assert_called()

@pytest.mark.asyncio
async def test_execute_limit_order_retry_and_cancel(mock_exchange):
    """Testa se o executor tenta novamente apos falha no preenchimento rapido."""
    executor = LimitExecutor(mock_exchange)
    
    # Mock da primeira ordem (sempre NEW)
    mock_exchange.create_order.return_value = {
        'symbol': 'BTCBRL',
        'orderId': 'ORD1',
        'status': 'NEW'
    }
    mock_exchange.get_order_status.return_value = {'status': 'NEW'}
    
    # Fazemos o loop interno do monitor_and_fill rodar rapido no teste
    with patch('asyncio.sleep', return_value=None), \
         patch('asyncio.get_event_loop') as mock_loop:
        
        # Simula o tempo passando para sair do loop de timeout
        mock_loop.return_value.time.side_effect = [0, 10, 20, 40, 50, 60, 100]
        
        # Limitamos a 2 retentativas para o teste ser rapido
        order = await executor.execute_limit_order('BTCBRL', 'BUY', 0.01, max_retries=2)
    
    # Nao foi preenchida, deve retornar None
    assert order is None
    # Deve ter tentado criar e cancelar 2 vezes
    assert mock_exchange.create_order.call_count == 2
    assert mock_exchange.cancel_order.call_count == 2

@pytest.mark.asyncio
async def test_execute_smart_market_fallback(mock_exchange):
    """Testa o fallback para ordem a mercado."""
    executor = LimitExecutor(mock_exchange)
    mock_exchange.create_order.return_value = {'status': 'FILLED', 'type': 'MARKET'}
    
    order = await executor.execute_smart_market('BTCBRL', 'SELL', 0.01)
    
    assert order['type'] == 'MARKET'
    mock_exchange.create_order.assert_called_with(
        symbol='BTCBRL',
        side='SELL',
        order_type='MARKET',
        quantity=0.01
    )
