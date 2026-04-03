# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
from logic.macro_radar import MacroRadar
from logic.strategist_agent import StrategistAgent

def test_macro_radar_risk_off():
    radar = MacroRadar()
    # DXY sobe 2% (Risco), SP500 cai 2% (Risco)
    score = radar.get_macro_score(0.02, -0.02, -0.5)
    assert score < 0.4
    mult, msg = radar.get_recommended_position_mult()
    assert mult <= 0.3

def test_strategist_agent_block_longs_on_high_risk():
    agent = StrategistAgent()
    # Caso de Risco Altissimo
    macro_data = {'dxy_change': 0.05, 'sp500_change': -0.05}
    signals = {'tier1': 0.1, 'tier2': 1} # Tier 2 quer comprar muito
    
    res = agent.run(signals, macro_data)
    
    # O agente deve ter reduzido o Tier 2 ou mudado a decisao
    assert res['risk_score'] < 0.3
    # Verificamos se houve mencao a Risco Sistemico no reasoning
    assert any("Risco Sistemico" in r or "Decision: WAIT" in r or res['decision'] != "EXECUTE_ALPHA" for r in res['reasoning'])

def test_strategist_assess_trade_logic():
    agent = StrategistAgent()
    # Mocking macro risk to low risk (Risk On)
    agent.radar.risk_score = 0.8
    
    # Probabilidade baixa
    dec, reason, mods = agent.assess_trade("BTCBRL", 1, 0.45, "Sinal Fraco")
    assert dec == "REJECT"
    
    # Probabilidade alta, macro ok
    dec, reason, mods = agent.assess_trade("BTCBRL", 1, 0.85, "Forte Reversao")
    assert dec == "APPROVE"
    assert mods['size_mult'] > 1.0
