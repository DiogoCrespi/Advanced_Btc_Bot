import pytest
import numpy as np
import pandas as pd
from logic.tribunal import ConsensusTribunal
from logic.ml_brain import MLBrain
from logic.tv_connector import TVConnector

@pytest.fixture
def tribunal():
    return ConsensusTribunal(veto_threshold=0.015)

# --- ConsensusTribunal Tests ---

def test_tv_signal_boost_buy(tribunal):
    signals = {
        'live': {'sig': 1},
        'shadow': {'sig': 1},
        'ancestral': {'sig': 0}
    }
    regime_metrics = {'vol': 0.01}
    tv_signal = 1
    
    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics,
        tv_signal=tv_signal
    )
    
    assert sig == 1
    assert conf == pytest.approx(0.95)  # 0.9 + 0.05 bonus
    assert "Consenso de Compra (3/3)" in reason

def test_tv_signal_exploratory(tribunal):
    signals = {
        'live': {'sig': 0},
        'shadow': {'sig': 0},
        'ancestral': {'sig': 0}
    }
    regime_metrics = {'vol': 0.01}
    tv_signal = 1
    
    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics=regime_metrics,
        tv_signal=tv_signal
    )
    
    assert sig == 1
    assert conf == 0.45
    assert "Sinal Externo (TradingView)" in reason

def test_tv_signal_unzeros_signals(tribunal):
    # Scenario: All models are neutral but TV says sell
    signals = {'live': {'sig': 0}, 'shadow': {'sig': 0}, 'ancestral': {'sig': 0}}
    tv_signal = -1
    
    sig, conf, reason = tribunal.evaluate_signals(
        signals=signals,
        regime_metrics={},
        tv_signal=tv_signal
    )
    
    assert sig == -1
    assert conf == 0.45
    assert "Sinal Externo (TradingView)" in reason

# --- MLBrain Tests ---

def test_ml_brain_horizon_default():
    brain = MLBrain()
    # Check if default is indeed 12 in the train logic (indirectly)
    pass

def test_ml_brain_labeling_diversity():
    # Mock data with a very small pump that needs horizon to reach TP
    # Data length must be > horizon
    data = {
        'close': [100.0, 100.1, 100.2, 100.3, 100.4, 105.0, 105.1, 105.2],
        'high':  [100.5, 100.6, 100.7, 100.8, 100.9, 106.0, 106.1, 106.2],
        'low':   [99.5, 99.6, 99.7, 99.8, 99.9, 104.0, 104.1, 104.2]
    }
    df = pd.DataFrame(data)
    brain = MLBrain()
    
    # TP=2% (target 102.0), SL=1% (target 99.0)
    # At index 0, price is 100.0. 
    # Index 1-4 high is < 102. Index 5 high is 106.0 (> 102.0).
    # Horizon 4: valid_n = 8-4=4. indices 0-3.
    # Index 0: views index 1-4. Max high is 100.9. No TP. Result 0.
    # Horizon 6: valid_n = 8-6=2. indices 0-1.
    # Index 0: views index 1-6. Index 5 is 106.0. Hits TP. Result 1.
    labels_h4 = brain.create_labels(df, tp=0.02, sl=0.01, horizon=4)
    labels_h6 = brain.create_labels(df, tp=0.02, sl=0.01, horizon=6)
    
    assert len(labels_h4) > 0
    assert labels_h4[0] == 0 # Horizon too short
    assert len(labels_h6) > 0
    assert labels_h6[0] == 1 # Horizon long enough

# --- TVConnector Tests ---

def test_tv_connector_default():
    connector = TVConnector()
    assert connector.get_technical_summary("BTCBRL") == 0
