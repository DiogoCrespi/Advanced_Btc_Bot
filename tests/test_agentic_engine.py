import sys
import os
import pytest
# Adiciona o diretorio raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from logic.macro_radar import MacroRadar
from logic.strategist_agent import StrategistAgent

def test_macro_radar_risk_off():
    radar = MacroRadar()
    # DXY sobe 3% (Risco), SP500 cai 3% (Risco), Ouro neutro, Noticias Neutras
    # Isso forca o score para baixo (< 0.35) para validar o modo Risk-Off
    score = radar.get_macro_score(0.03, -0.03, 0, 0)
    
    # 0.5 - (0.03*10) = 0.2
    # 0.5 + (-0.03*5) = 0.35
    # (0.2*0.35) + (0.35*0.35) + (0.5*0.15) + (0.5*0.15) = 0.07 + 0.1225 + 0.075 + 0.075 = 0.3425
    assert score < 0.35
    
    mult, msg = radar.get_recommended_position_mult()
    assert mult <= 0.4
    assert "Risk Off" in msg

def test_strategist_agent_block_longs_on_high_risk():
    agent = StrategistAgent()
    # Caso de Risco Altissimo (Score < 0.25)
    # DXY +5%, SP500 -10%
    macro_data = {'dxy_change': 0.05, 'sp500_change': -0.1, 'gold_change': 0, 'news_sentiment': -1}
    signals = {'tier1': 0.1, 'tier2': 1} 
    
    res = agent.run(signals, macro_data)
    
    # O agente deve ter bloqueado os sinais e reduzido o score
    assert res['risk_score'] < 0.25
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
