import pytest
from logic.tribunal import ConsensusTribunal

@pytest.fixture
def tribunal():
    return ConsensusTribunal(veto_threshold=0.015)

def test_macro_veto(tribunal):
    signals = {'live': {'sig': 1, 'prob': 0.8}}
    regime_metrics = {'vol': 0.01}
    macro_status = {'is_extreme': True, 'reason': 'Hostile Environment'}

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics,
        macro_status=macro_status
    )

    assert sig == 0
    assert conf == 0.1
    assert reason == "VETO MACRO: Hostile Environment"

def test_macro_veto_not_applied_for_sell(tribunal):
    # Macro veto only blocks buy signals
    signals = {'live': {'sig': -1, 'prob': 0.8}, 'shadow': {'sig': -1}, 'ancestral': {'sig': -1}}
    regime_metrics = {'vol': 0.01}
    macro_status = {'is_extreme': True, 'reason': 'Hostile Environment'}

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics,
        macro_status=macro_status
    )

    assert sig == -1
    assert conf == 1.0
    assert "Consenso de Venda" in reason

def test_failure_analogy_veto(tribunal):
    signals = {'live': {'sig': 1, 'prob': 0.8}}
    regime_metrics = {'vol': 0.01}

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics,
        failure_risk=2
    )

    assert sig == 0
    assert conf == 0.2
    assert reason == "VETO DE PROBABILIDADE: Estado similar a 2 falhas passadas."

def test_ancestral_veto_divergence(tribunal):
    # High volatility, ancestral disagrees with live (and is not 0)
    signals = {
        'live': {'sig': 1, 'prob': 0.8},
        'shadow': {'sig': 1, 'prob': 0.8},
        'ancestral': {'sig': -1, 'prob': 0.8}
    }
    regime_metrics = {'vol': 0.02} # > 0.015

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics
    )

    assert sig == 0
    assert conf == 0.4
    assert reason == "VETO ANCESTRAL: Divergencia em Alta Volatilidade"

def test_ancestral_veto_caution(tribunal):
    # High volatility, ancestral is 0, live is not 0
    signals = {
        'live': {'sig': 1, 'prob': 0.8},
        'shadow': {'sig': 1, 'prob': 0.8},
        'ancestral': {'sig': 0, 'prob': 0.0}
    }
    regime_metrics = {'vol': 0.02} # > 0.015

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics
    )

    assert sig == 0
    assert conf == 0.3
    assert reason == "VETO ANCESTRAL: Veterano recomenda cautela (Ficar de Fora)"

def test_consensus_neutral(tribunal):
    signals = {
        'live': {'sig': 0, 'prob': 0.4},
        'shadow': {'sig': 0, 'prob': 0.0},
        'ancestral': {'sig': 0, 'prob': 0.0}
    }
    regime_metrics = {'vol': 0.01}

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics
    )

    assert sig == 0
    assert conf == 0.4  # fallback uses live_prob
    assert reason == "Consenso: Neutro"

def test_consensus_buy_strong(tribunal):
    signals = {
        'live': {'sig': 1},
        'shadow': {'sig': 1},
        'ancestral': {'sig': 1}
    }
    regime_metrics = {'vol': 0.01}

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics
    )

    assert sig == 1
    assert conf == 1.0
    assert reason == "Consenso de Compra (3/3)"

def test_consensus_buy_weak(tribunal):
    signals = {
        'live': {'sig': 1},
        'shadow': {'sig': 1},
        'ancestral': {'sig': 0}
    }
    regime_metrics = {'vol': 0.01}

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics
    )

    assert sig == 1
    assert conf == 0.7
    assert reason == "Consenso de Compra (2/3)"

def test_consensus_sell_strong(tribunal):
    signals = {
        'live': {'sig': -1},
        'shadow': {'sig': -1},
        'ancestral': {'sig': -1}
    }
    regime_metrics = {'vol': 0.01}

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics
    )

    assert sig == -1
    assert conf == 1.0
    assert reason == "Consenso de Venda (3/3)"

def test_total_conflict(tribunal):
    signals = {
        'live': {'sig': 1},
        'shadow': {'sig': -1},
        'ancestral': {'sig': 0}
    }
    regime_metrics = {'vol': 0.01}

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics
    )

    assert sig == 0
    assert conf == 0.2
    assert reason == "CONFLITO: Modelos divergem completamente"

def test_isolated_signal(tribunal):
    signals = {
        'live': {'sig': 1},
        'shadow': {'sig': 0},
        'ancestral': {'sig': 0}
    }
    regime_metrics = {'vol': 0.01}

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics
    )

    assert sig == 1
    assert conf == 0.5
    assert reason == "Sinal Isolado (Sem Consenso)"

def test_indecisao_colegiada(tribunal):
    signals = {
        'live': {'sig': 1},
        'shadow': {'sig': -1},
        'ancestral': {'sig': 1} # 2 buy, 1 sell, buy_votes >= 2 so this will be caught by buy consensus
    }
    # To hit indecisao_colegiada, we need not neutral (active_sigs > 0)
    # not buy_votes >= 2
    # not sell_votes >= 2
    # not buy_votes == 1 and sell_votes == 1
    # not len(active_sigs) == 1
    # The only way to bypass all is if there are 3 active sigs, but neither buy nor sell is >= 2 and it's not 1 buy and 1 sell.
    # Wait, 3 active sigs must mean either 2 of them are the same or all 3 are the same.
    # If active_sigs == 3, buy_votes + sell_votes = 3.
    # So either buy is 2+, or sell is 2+.
    # Thus, this branch is unreachable if signals only take values -1, 0, 1!
    # Wait, what if someone sends a signal of 2 or -2?
    signals = {
        'live': {'sig': 2},
        'shadow': {'sig': -2},
        'ancestral': {'sig': 3}
    }
    regime_metrics = {'vol': 0.01}

    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics
    )

    assert sig == 0
    assert conf == 0.1
    assert reason == "Indecisao Colegiada"
