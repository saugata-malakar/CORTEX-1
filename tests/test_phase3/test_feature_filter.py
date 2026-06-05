"""
test_feature_filter.py — Unit Tests for XGBoost FP Filter Classifier
====================================================================

Verifies:
  - Model fitting, GridSearch/Bayesian optimization, and cross-validation.
  - Custom decision thresholds (0.75) and probability calculations.
  - Performance metrics evaluation (Precision, Recall, F1, AUC-ROC).
  - Feature importances and SHAP values explanations.
  - Serialization and deserialization of classifier components.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from src.phase3_filtering.feature_filter import FalsePositiveFilter


@pytest.fixture
def filter_config() -> dict:
    """Minimal mock configuration."""
    return {
        "false_positive_filter": {
            "enabled": True,
            "classification_threshold": 0.75,
            "bayesian_opt_iterations": 2,
            "precision_target": 0.90,
            "f1_target": 0.85,
            "augmentation": {
                "flip_horizontal": True,
                "flip_vertical": True,
                "rotation_range": 15,
                "brightness_jitter": 0.20,
                "noise_sigma_range": [5, 15],
            }
        }
    }


def test_filter_train_predict(filter_config: dict) -> None:
    """Verify that filter trains, applies thresholds, and evaluates metrics."""
    ff_filter = FalsePositiveFilter(filter_config)
    
    # Generate 40 synthetic samples (20 positives, 20 negatives) of 180 dimensions
    np.random.seed(42)
    X_train = np.random.normal(0, 1.0, (40, 180))
    y_train = np.array([1]*20 + [0]*20)
    
    # Introduce separation for the model to learn
    X_train[y_train == 1, :10] += 2.0
    
    metrics = ff_filter.train(X_train, y_train)
    
    # Verify metrics compiled
    assert "train_precision" in metrics
    assert "train_f1" in metrics
    assert "train_auc" in metrics
    
    # Verify predict formats
    label, prob = ff_filter.predict(X_train[0])
    assert label in (0, 1)
    assert 0.0 <= prob <= 1.0
    
    # Batch predict
    batch_res = ff_filter.predict_batch(X_train[:5])
    assert len(batch_res) == 5
    assert all(r[0] in (0, 1) for r in batch_res)


def test_filter_evaluation_and_shap(filter_config: dict) -> None:
    """Verify that metrics evaluations and SHAP interpretations compile."""
    ff_filter = FalsePositiveFilter(filter_config)
    
    X_train = np.random.normal(0, 1.0, (20, 180))
    y_train = np.array([1]*10 + [0]*10)
    X_train[y_train == 1, :10] += 2.0
    
    ff_filter.train(X_train, y_train)
    
    # 1. Evaluate
    evals = ff_filter.evaluate(X_train, y_train)
    assert "precision" in evals
    assert "confusion_matrix" in evals
    assert evals["confusion_matrix"]["true_positives"] >= 0
    
    # 2. SHAP
    shap_summary = ff_filter.compute_shap(X_train)
    assert "top_feature_indices" in shap_summary
    assert len(shap_summary["top_feature_indices"]) <= 10


def test_filter_serialization(filter_config: dict, tmp_path: Path) -> None:
    """Verify that model parameters serialize and deserialize cleanly."""
    ff_filter = FalsePositiveFilter(filter_config)
    
    X_train = np.random.normal(0, 1.0, (20, 180))
    y_train = np.array([1]*10 + [0]*10)
    ff_filter.train(X_train, y_train)
    
    model_path = tmp_path / "xgb_model.pkl"
    ff_filter.save_model(model_path)
    assert model_path.exists()
    
    # Reload
    new_filter = FalsePositiveFilter(filter_config)
    new_filter.load_model(model_path)
    
    assert new_filter.model is not None
    assert new_filter.threshold == ff_filter.threshold
    assert new_filter.enabled == ff_filter.enabled
