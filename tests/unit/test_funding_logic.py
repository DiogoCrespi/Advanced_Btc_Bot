# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import sys
import os

# Adiciona o diretorio 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from logic.funding_logic import FundingLogic

def test_funding_logic_enter_signal():
    """Testa o sinal de entrada quando a taxa de funding anualizada supera a taxa livre de risco."""
    logic = FundingLogic(risk_free_rate_annual=0.10)

    # 0.0001 * 3 * 365 = 0.1095 (10.95% anual), que e maior que 0.10 (10%)
    current_funding_8h = 0.0001
    historical_fundings = []

    signal = logic.get_signal(current_funding_8h, historical_fundings)
    assert signal == 1

def test_funding_logic_exit_signal():
    """Testa o sinal de saida quando as ultimas 5 taxas de funding sao negativas."""
    logic = FundingLogic(risk_free_rate_annual=0.10)

    # Taxa atual baixa para nao acionar sinal de entrada
    current_funding_8h = 0.00001
    historical_fundings = [-0.01, -0.02, -0.005, -0.001, -0.003]

    signal = logic.get_signal(current_funding_8h, historical_fundings)
    assert signal == 0

def test_funding_logic_no_signal_insufficient_history():
    """Testa que nenhum sinal de saida e gerado com menos de 5 historicos negativos."""
    logic = FundingLogic(risk_free_rate_annual=0.10)

    current_funding_8h = 0.00001
    historical_fundings = [-0.01, -0.02, -0.005, -0.001] # Apenas 4

    signal = logic.get_signal(current_funding_8h, historical_fundings)
    assert signal is None

def test_funding_logic_no_signal_mixed_history():
    """Testa que nenhum sinal de saida e gerado se o historico recente tiver um valor positivo."""
    logic = FundingLogic(risk_free_rate_annual=0.10)

    current_funding_8h = 0.00001
    # 5 valores, mas o terceiro e positivo
    historical_fundings = [-0.01, -0.02, 0.005, -0.001, -0.003]

    signal = logic.get_signal(current_funding_8h, historical_fundings)
    assert signal is None

def test_funding_logic_history_length_greater_than_5():
    """Testa o comportamento com mais de 5 valores historicos."""
    logic = FundingLogic(risk_free_rate_annual=0.10)

    current_funding_8h = 0.00001
    # Mais de 5 valores. Os ultimos 5 sao negativos.
    historical_fundings = [0.1, 0.2, -0.01, -0.02, -0.005, -0.001, -0.003]

    signal = logic.get_signal(current_funding_8h, historical_fundings)
    assert signal == 0

def test_funding_logic_enter_signal_priority():
    """Testa se o sinal de entrada tem prioridade sobre o historico negativo."""
    logic = FundingLogic(risk_free_rate_annual=0.10)

    current_funding_8h = 0.0001 # Vai acionar entrada
    historical_fundings = [-0.01, -0.02, -0.005, -0.001, -0.003] # Acionaria saida se avaliado

    signal = logic.get_signal(current_funding_8h, historical_fundings)
    assert signal == 1
