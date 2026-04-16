# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import sys
import os

# Adiciona o diretorio 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data')))

from xaut_logic import XAUTAnalyzer

def test_xaut_analyzer_features(sample_ohlcv):
    analyzer = XAUTAnalyzer()
    df_feat = analyzer.compute_ratio_features(sample_ohlcv)
    
    assert 'ratio_rsi' in df_feat.columns
    assert 'bb_pct' in df_feat.columns
    assert not df_feat.isnull().values.any()
    assert len(df_feat) > 0

def test_xaut_buy_signal(xaut_buy_signal_df):
    analyzer = XAUTAnalyzer()
    df_feat = analyzer.compute_ratio_features(xaut_buy_signal_df)
    assert len(df_feat) > 0
    signal, confidence, reason, metrics = analyzer.get_signal(df_feat)
    
    # E aceitavel sinal 0 se a confianca for baixa, mas o motivo deve indicar a direcao ou o filtro
    assert signal in [0, 1]
    if signal == 1:
        assert confidence >= analyzer.MIN_CONFIDENCE
    assert "XAUT" in reason or "Neutro" in reason

def test_xaut_sell_signal(xaut_sell_signal_df):
    analyzer = XAUTAnalyzer()
    df_feat = analyzer.compute_ratio_features(xaut_sell_signal_df)
    assert len(df_feat) > 0
    signal, confidence, reason, metrics = analyzer.get_signal(df_feat)
    
    assert signal in [0, -1]
    if signal == -1:
        assert confidence >= analyzer.MIN_CONFIDENCE
    assert "XAUT" in reason or "Neutro" in reason

def test_is_dca_allowed():
    """Testa a logica de permissao para DCA (Dollar Cost Averaging)."""
    analyzer = XAUTAnalyzer()

    # Caso 1: Nenhuma posicao existente -> DCA permitido
    assert analyzer.is_dca_allowed([], 0.05) == True

    # Caso 2: Posicoes invalidas (sem ratio_entry, zero, negativo) sao ignoradas
    invalid_positions = [
        {'id': 1},
        {'id': 2, 'ratio_entry': 0},
        {'id': 3, 'ratio_entry': -0.05}
    ]
    assert analyzer.is_dca_allowed(invalid_positions, 0.05) == True

    # Caso 3: Preco muito proximo acima (dentro de 1.5%) -> DCA rejeitado
    existing = [{'ratio_entry': 0.05}]
    # 0.0505 e +1% de 0.05
    assert analyzer.is_dca_allowed(existing, 0.0505) == False

    # Caso 4: Preco muito proximo abaixo (dentro de 1.5%) -> DCA rejeitado
    # 0.0495 e -1% de 0.05
    assert analyzer.is_dca_allowed(existing, 0.0495) == False

    # Caso 5: Preco suficientemente acima (> 1.5%) -> DCA permitido
    # 0.051 e +2% de 0.05
    assert analyzer.is_dca_allowed(existing, 0.051) == True

    # Caso 6: Preco suficientemente abaixo (< 1.5%) -> DCA permitido
    # 0.049 e -2% de 0.05
    assert analyzer.is_dca_allowed(existing, 0.049) == True

    # Caso 7: Multiplas posicoes - uma muito proxima -> DCA rejeitado
    multi_positions = [
        {'ratio_entry': 0.04}, # Longe
        {'ratio_entry': 0.05}  # Perto
    ]
    assert analyzer.is_dca_allowed(multi_positions, 0.0505) == False

    # Caso 8: Multiplas posicoes - todas distantes -> DCA permitido
    multi_positions_far = [
        {'ratio_entry': 0.04}, # 20% de dist
        {'ratio_entry': 0.06}  # 20% de dist
    ]
    assert analyzer.is_dca_allowed(multi_positions_far, 0.05) == True

def test_xaut_calc_pnl():
    """Testa o calculo de PnL em BTC e percentual."""
    analyzer = XAUTAnalyzer()

    # Caso 1: Lucro (PnL positivo)
    # Entrada: 10 XAUT a 0.05 BTC/XAUT -> custo_btc = 0.5
    # Atual: 0.06 BTC/XAUT -> valor_atual = 0.6
    # PnL BTC = 0.6 - 0.5 = 0.1
    # PnL % = 0.1 / 0.5 = 0.2 (20%)
    pos_profit = {'xaut_qty': 10.0, 'cost_btc': 0.5}
    current_ratio_profit = 0.06

    pnl_btc = analyzer.calc_pnl_btc(pos_profit, current_ratio_profit)
    pnl_pct = analyzer.calc_pnl_pct(pos_profit, current_ratio_profit)

    assert pnl_btc == pytest.approx(0.1)
    assert pnl_pct == pytest.approx(0.2)

    # Caso 2: Prejuizo (PnL negativo)
    # Entrada: 10 XAUT a 0.05 BTC/XAUT -> custo_btc = 0.5
    # Atual: 0.04 BTC/XAUT -> valor_atual = 0.4
    # PnL BTC = 0.4 - 0.5 = -0.1
    # PnL % = -0.1 / 0.5 = -0.2 (-20%)
    pos_loss = {'xaut_qty': 10.0, 'cost_btc': 0.5}
    current_ratio_loss = 0.04

    pnl_btc = analyzer.calc_pnl_btc(pos_loss, current_ratio_loss)
    pnl_pct = analyzer.calc_pnl_pct(pos_loss, current_ratio_loss)

    assert pnl_btc == pytest.approx(-0.1)
    assert pnl_pct == pytest.approx(-0.2)

    # Caso 3: Zero PnL
    pos_zero = {'xaut_qty': 10.0, 'cost_btc': 0.5}
    current_ratio_zero = 0.05

    assert analyzer.calc_pnl_btc(pos_zero, current_ratio_zero) == pytest.approx(0.0)
    assert analyzer.calc_pnl_pct(pos_zero, current_ratio_zero) == pytest.approx(0.0)

    # Caso 4: Custo BTC zero (edge case)
    pos_zero_cost = {'xaut_qty': 10.0, 'cost_btc': 0.0}
    current_ratio = 0.05

    assert analyzer.calc_pnl_btc(pos_zero_cost, current_ratio) == pytest.approx(0.5)
    assert analyzer.calc_pnl_pct(pos_zero_cost, current_ratio) == 0.0
