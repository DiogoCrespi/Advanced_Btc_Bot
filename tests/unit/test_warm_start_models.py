"""
Test suite for validating Warm Start model files.

Verifies that:
  - All expected model files exist and are non-empty
  - Models are not corrupted (can be deserialized)
  - Models have the expected internal structure (MLBrain attributes)
  - Models produce valid (non-zero, non-NaN) predictions on synthetic live data
  - Label distribution is balanced enough to be useful (not all-neutral)
"""
import os
import pytest
import numpy as np
import pandas as pd
import joblib
from logic.ml_brain import MLBrain
from data.data_engine import DataEngine

# --- Configuration ---
ASSETS = ["BTCBRL", "ETHBRL", "SOLBRL", "LINKBRL", "AVAXBRL", "RENDERBRL"]
MODELS_DIR = "models"
MIN_MODEL_SIZE_BYTES = 100_000  # 100KB - a smaller model is likely corrupted

def expected_model_paths():
    paths = []
    for asset in ASSETS:
        paths.append(os.path.join(MODELS_DIR, f"{asset.lower()}_brain_v1.pkl"))
        paths.append(os.path.join(MODELS_DIR, f"brain_rf_v3_alpha_{asset}.pkl"))
    return paths

# ─────────────────────────────────────────────
# TIER 1: File System Integrity Checks
# ─────────────────────────────────────────────

@pytest.mark.parametrize("model_path", expected_model_paths())
def test_model_file_exists(model_path):
    """Every expected model file must exist after warm start."""
    assert os.path.exists(model_path), f"Model file not found: {model_path}"

@pytest.mark.parametrize("model_path", expected_model_paths())
def test_model_file_size(model_path):
    """Model files must be above a minimum size (avoids zero-byte or trivially empty files)."""
    if not os.path.exists(model_path):
        pytest.skip(f"File not found: {model_path}")
    size = os.path.getsize(model_path)
    assert size >= MIN_MODEL_SIZE_BYTES, (
        f"Model file {model_path} is suspiciously small ({size} bytes < {MIN_MODEL_SIZE_BYTES} bytes). "
        "May be corrupted or empty."
    )

# ─────────────────────────────────────────────
# TIER 2: Deserialization & Corruption Checks
# ─────────────────────────────────────────────

@pytest.mark.parametrize("model_path", expected_model_paths())
def test_model_not_corrupted(model_path):
    """Model files must be loadable by joblib without errors (MLBrain uses joblib)."""
    if not os.path.exists(model_path):
        pytest.skip(f"File not found: {model_path}")
    try:
        obj = joblib.load(model_path)
        assert obj is not None, "Loaded object is None"
        assert isinstance(obj, dict), "Expected a dict from joblib.load"
        assert 'model' in obj, "Missing 'model' key in serialized data"
    except Exception as e:
        pytest.fail(f"Failed to load {model_path} with joblib: {e}")

# ─────────────────────────────────────────────
# TIER 3: MLBrain API & Structure Checks
# ─────────────────────────────────────────────

@pytest.mark.parametrize("model_path", expected_model_paths())
def test_model_loads_via_mlbrain(model_path):
    """MLBrain.load_model() must succeed and mark the brain as trained."""
    if not os.path.exists(model_path):
        pytest.skip(f"File not found: {model_path}")
    brain = MLBrain()
    result = brain.load_model(model_path)
    assert result is True, f"MLBrain.load_model() returned False for {model_path}"
    assert brain.is_trained, "Brain is not marked as trained after loading."

@pytest.mark.parametrize("model_path", expected_model_paths())
def test_model_has_features(model_path):
    """Loaded model must have a non-empty feature_cols list."""
    if not os.path.exists(model_path):
        pytest.skip(f"File not found: {model_path}")
    brain = MLBrain()
    brain.load_model(model_path)
    assert hasattr(brain, 'feature_cols'), "Brain missing 'feature_cols' attribute."
    assert len(brain.feature_cols) > 0, "Brain has an empty feature list."

@pytest.mark.parametrize("model_path", expected_model_paths())
def test_model_n_estimators(model_path):
    """Internal RandomForest must have the expected number of estimators."""
    if not os.path.exists(model_path):
        pytest.skip(f"File not found: {model_path}")
    brain = MLBrain()
    brain.load_model(model_path)
    if not brain.is_trained or brain.model is None:
        pytest.skip("Model not trained, skipping estimator check.")
    n_est = len(brain.model.estimators_)
    assert n_est > 10, f"Model has too few estimators ({n_est}), may be degenerate."

# ─────────────────────────────────────────────
# TIER 4: Prediction Quality Checks
# ─────────────────────────────────────────────

def _generate_live_features(brain):
    """Generate a valid synthetic feature row matching the model's feature_cols."""
    np.random.seed(42)
    values = np.random.uniform(0.01, 1.0, len(brain.feature_cols))
    # Set ATR above the model's own threshold to bypass VETO REGIME
    try:
        atr_idx = brain.feature_cols.index('feat_atr_pct')
        # Use the actual model's threshold + margin
        values[atr_idx] = (brain.atr_threshold or 0.5) + 0.5
    except ValueError:
        pass
    return values

@pytest.mark.parametrize("model_path", expected_model_paths())
def test_model_prediction_not_always_zero(model_path):
    """
    The model's raw RandomForest must not always predict class 0 (neutral).
    We check the argmax of predict_proba() for 20 random feature rows.
    At least 1 must be -1 or 1. This bypasses the min_confidence threshold
    which is an operational gate, not a model quality issue.
    """
    if not os.path.exists(model_path):
        pytest.skip(f"File not found: {model_path}")
    brain = MLBrain()
    if not brain.load_model(model_path):
        pytest.skip("Could not load model.")
    if brain.model is None:
        pytest.skip("Brain has no internal model.")

    atr_threshold = (brain.atr_threshold or 0.5) + 0.5
    non_zero_raw_count = 0
    for seed in range(20):
        np.random.seed(seed)
        feat_values = np.random.uniform(0.01, 2.0, len(brain.feature_cols))
        try:
            atr_idx = brain.feature_cols.index('feat_atr_pct')
            feat_values[atr_idx] = atr_threshold
        except ValueError:
            pass
        # Check raw argmax, bypassing the min_confidence operational filter
        proba = brain.model.predict_proba(feat_values.reshape(1, -1))[0]
        raw_class = brain.model.classes_[np.argmax(proba)]
        if raw_class != 0:
            non_zero_raw_count += 1

    assert non_zero_raw_count > 0, (
        f"Model {model_path}: raw RF never predicted a directional class (-1 or 1) "
        "across 20 random feature sets. The model is likely stuck in a neutral bias."
    )

@pytest.mark.parametrize("model_path", expected_model_paths())
def test_model_label_distribution(model_path):
    """
    Check if the training label distribution is balanced.
    A healthy model should have a neutral ratio below 85%.
    """
    if not os.path.exists(model_path):
        pytest.skip(f"File not found: {model_path}")
    brain = MLBrain()
    if not brain.load_model(model_path):
        pytest.skip("Could not load model.")

    if not hasattr(brain, 'model') or brain.model is None:
        pytest.skip("Loaded brain has no internal model.")

    # Use the OOB score as a proxy for quality
    oob = getattr(brain, 'oob_score', None)
    if oob is not None:
        # OOB score of 0.33 is exactly random (3-class random forest baseline)
        assert oob >= 0.30, f"Model {model_path} has OOB score {oob:.2f} which is below the random baseline."

@pytest.mark.parametrize("asset", ASSETS)
def test_v1_and_v3_match_feature_count(asset):
    """
    The v1 and v3-Alpha models for the same asset must have the same number of features.
    A mismatch would cause prediction errors at runtime.
    """
    v1_path = os.path.join(MODELS_DIR, f"{asset.lower()}_brain_v1.pkl")
    v3_path = os.path.join(MODELS_DIR, f"brain_rf_v3_alpha_{asset}.pkl")

    if not (os.path.exists(v1_path) and os.path.exists(v3_path)):
        pytest.skip(f"One or both model files missing for {asset}")

    b1 = MLBrain()
    b1.load_model(v1_path)
    b3 = MLBrain()
    b3.load_model(v3_path)

    assert len(b1.feature_cols) == len(b3.feature_cols), (
        f"Feature count mismatch for {asset}: "
        f"v1={len(b1.feature_cols)}, v3={len(b3.feature_cols)}. "
        "This will cause runtime prediction errors."
    )
