import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from multicore_master_bot import MulticoreMasterBot
from logic.execution.backtest_engine import BacktestEngine

@pytest.mark.asyncio
async def test_balance_sync_integration_with_backtest():
    """Teste de integracao garantindo que o bot inicializa e sincroniza saldos corretamente."""
    
    # Usamos o BacktestEngine como mock da exchange real
    engine = BacktestEngine(initial_balance=1234.56)
    
    with patch('multicore_master_bot.DataEngine'), \
         patch('multicore_master_bot.MLBrain'), \
         patch('multicore_master_bot.LocalOracle'), \
         patch('multicore_master_bot.Watchdog'), \
         patch('multicore_master_bot.BinanceLive', return_value=engine):
        
        # Inicializa o bot em modo live para disparar a logica de sincronizacao
        bot = MulticoreMasterBot(mode="live")
        
        # Mock do initialize da exchange
        bot.exchange.initialize = AsyncMock()
        
        # No main(), a sincronizacao acontece
        from multicore_master_bot import main
        
        # Mock de outras tarefas de background para o teste nao rodar infinitamente
        with patch('multicore_master_bot.WebSocketSupervisor.start', return_value=asyncio.sleep(0.1)), \
             patch('multicore_master_bot.MulticoreMasterBot._train_initial_evo_pop', return_value=asyncio.sleep(0.1)), \
             patch('multicore_master_bot.LocalOracle.start_loop', return_value=asyncio.sleep(0.1)), \
             patch('multicore_master_bot.MulticoreMasterBot.run_async', return_value=asyncio.sleep(0.1)):
            
            # Inicializa a listen key e faz o primeiro sync
            bot.listen_key = await bot.exchange.start_user_data_stream()
            await bot.sync_balances_from_exchange()
            
            # Verifica se o bot pegou o saldo do motor de backtest (simulando a exchange)
            assert bot.balance == 1234.56
            assert bot.listen_key == "mock_listen_key"
            
            # Simula mudanca de saldo no motor e pede sync
            engine.balances['BRL'] = 9999.99
            await bot.sync_balances_from_exchange()
            assert bot.balance == 9999.99
