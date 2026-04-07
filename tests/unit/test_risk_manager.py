import pytest
from logic.risk_manager import RiskManager

def test_check_liquidation_risk_leverage_1_or_less():
    rm = RiskManager()

    # Test with leverage 1.0
    distance, liq_price = rm.check_liquidation_risk(entry_price=50000, current_price=45000, leverage=1.0)
    assert distance == 1.0
    assert liq_price == 999999999

    # Test with leverage < 1.0 (e.g. 0.5)
    distance, liq_price = rm.check_liquidation_risk(entry_price=50000, current_price=45000, leverage=0.5)
    assert distance == 1.0
    assert liq_price == 999999999

def test_check_liquidation_risk_leverage_2():
    rm = RiskManager()

    # Leverage = 2.0
    # Liquidation price = entry * (2 / (2 - 1)) = entry * 2 = 100000
    # Current = 50000
    # distance = (100000 - 50000) / 50000 = 1.0 (100% away)
    distance, liq_price = rm.check_liquidation_risk(entry_price=50000, current_price=50000, leverage=2.0)
    assert liq_price == 100000.0
    assert distance == 1.0

    # Current = 75000
    # distance = (100000 - 75000) / 75000 = 25000 / 75000 = 0.3333333333333333
    distance, liq_price = rm.check_liquidation_risk(entry_price=50000, current_price=75000, leverage=2.0)
    assert liq_price == 100000.0
    assert abs(distance - 0.3333333333333333) < 1e-9

def test_check_liquidation_risk_leverage_10():
    rm = RiskManager()

    # Leverage = 10.0
    # Liquidation price = 50000 * (10 / 9) = 55555.555555555555
    # Current = 50000
    # distance = (55555.555555555555 - 50000) / 50000 = 5555.555555555555 / 50000 = 0.1111111111111111
    distance, liq_price = rm.check_liquidation_risk(entry_price=50000, current_price=50000, leverage=10.0)
    expected_liq_price = 50000 * (10.0 / 9.0)
    assert liq_price == expected_liq_price
    assert abs(distance - 0.1111111111111111) < 1e-9
