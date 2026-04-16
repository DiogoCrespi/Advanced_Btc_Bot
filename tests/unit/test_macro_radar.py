import pytest
from logic.macro_radar import MacroRadar

def test_get_macro_score_neutral():
    radar = MacroRadar()
    score = radar.get_macro_score(0.0, 0.0, 0.0, 0.0)
    assert score == pytest.approx(0.5)

def test_get_macro_score_extreme_positive():
    radar = MacroRadar()
    score = radar.get_macro_score(-0.05, 0.1, 0.1, 1.0)
    assert score == pytest.approx(1.0)

def test_get_macro_score_extreme_negative():
    radar = MacroRadar()
    score = radar.get_macro_score(0.05, -0.1, -0.1, -1.0)
    assert score == pytest.approx(0.0)

def test_get_macro_score_clamping():
    radar = MacroRadar()
    score_high = radar.get_macro_score(-1.0, 1.0, 1.0, 1.0)
    assert score_high == pytest.approx(1.0)

    score_low = radar.get_macro_score(1.0, -1.0, -1.0, -1.0)
    assert score_low == pytest.approx(0.0)

def test_is_risk_off_extreme():
    radar = MacroRadar()

    is_extreme, reason = radar.is_risk_off_extreme(0.006, 0.0)
    assert is_extreme is True
    assert "DXY RIPPING" in reason

    is_extreme, reason = radar.is_risk_off_extreme(0.0, -0.015)
    assert is_extreme is True
    assert "SP500 DUMPING" in reason

    is_extreme, reason = radar.is_risk_off_extreme(0.0, 0.0)
    assert is_extreme is False
    assert reason is None

def test_get_recommended_position_mult():
    radar = MacroRadar()

    radar.risk_score = 0.3
    mult, reason = radar.get_recommended_position_mult()
    assert mult == 0.4
    assert "Macro Risk Off" in reason

    radar.risk_score = 0.7
    mult, reason = radar.get_recommended_position_mult()
    assert mult == 1.3
    assert "Macro Risk On" in reason

    radar.risk_score = 0.5
    mult, reason = radar.get_recommended_position_mult()
    assert mult == 1.0
    assert "Macro Neutro" in reason
