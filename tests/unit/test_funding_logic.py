import pytest
import sys
import os

# Adiciona o diretorio raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from logic.funding_logic import FundingLogic

def test_calculate_annualized_funding_positive():
    logic = FundingLogic()
    # 0.01% por 8h = 0.0001
    rate_8h = 0.0001
    expected = rate_8h * 3 * 365
    assert logic.calculate_annualized_funding(rate_8h) == pytest.approx(expected)

def test_calculate_annualized_funding_zero():
    logic = FundingLogic()
    assert logic.calculate_annualized_funding(0.0) == 0.0

def test_calculate_annualized_funding_negative():
    logic = FundingLogic()
    rate_8h = -0.0005
    expected = rate_8h * 3 * 365
    assert logic.calculate_annualized_funding(rate_8h) == pytest.approx(expected)

def test_get_signal_enter_long():
    # Se a taxa anualizada for maior que risk_free_rate_annual
    logic = FundingLogic(risk_free_rate_annual=0.10)
    # rate_8h que da > 10% a.a. => 0.10 / (3 * 365) = 0.0000913
    rate_8h = 0.0002 # 0.02% a cada 8h -> 21.9% ao ano
    assert logic.get_signal(rate_8h, []) == 1

def test_get_signal_exit():
    logic = FundingLogic(risk_free_rate_annual=0.10)
    # 5 ciclos de funding negativo
    historical = [-0.0001, -0.0002, -0.0001, -0.0003, -0.0001]
    # current_funding nao atende a regra de entrada (ex: 0)
    assert logic.get_signal(0.0, historical) == 0

def test_get_signal_no_action():
    logic = FundingLogic(risk_free_rate_annual=0.10)
    # Taxa anualizada menor ou igual a risk_free_rate_annual
    # e menos de 5 historicos negativos
    rate_8h = 0.00005 # 5.4% ao ano
    historical = [-0.0001, 0.0001, -0.0001]
    assert logic.get_signal(rate_8h, historical) is None

def test_get_signal_no_action_5_cycles_mixed():
    logic = FundingLogic(risk_free_rate_annual=0.10)
    # 5 ciclos, mas nao todos negativos
    historical = [-0.0001, -0.0002, 0.0001, -0.0003, -0.0001]
    assert logic.get_signal(0.0, historical) is None
