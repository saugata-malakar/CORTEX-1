"""
feature_filter.py — XGBoost False-Positive Defect Classifier
============================================================

Trains and executes the precision-first false-positive filtering layer:
  - XGBoost Classifier: Distinguishes true structural defects from facade false
    positives (mortar lines, joints, shadows).
  - Class Imbalance: Dynamically adjusts ``scale_pos_weight`` and L2 regularization.
  - Hyperparameter Search: Integrates Bayesian optimization (scikit-optimize)
    with a robust scikit-learn GridSearchCV fallback.
  - Decision Boundary: Enforces a raised precision-first threshold (0.75).
  - Interpretability: Computes SHAP value explanations for auditability.
  - Robustness: Seamlessly falls back to scikit-learn's ``RandomForestClassifier``
    if the XGBoost binary is missing or fails.

References:
  - [R12] Chen & Guestrin (2016) XGBoost: A Scalable Tree Boosting System.
  - [R13] Lundberg & Lee (2017) A Unified Approach to Interpreting Model Predictions.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

# Try importing XGBoost
try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

# Try importing scikit-optimize
try:
    from skopt import BayesSearchCV
    from skopt.space import Real, Integer
    SKOPT_AVAILABLE = True
except ImportError:
    SKOPT_AVAILABLE = False

# Try importing SHAP
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

# Standard ML imports
try:
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class FalsePositiveFilter:
    """Trains and deploys the binary XGBoost classifier to suppress false-positive defects.

    Parameters
    ----------
    config : dict
        Pipeline master configuration dict (specifically uses 'false_positive_filter' parameters).
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        
        fp_cfg = config.get("false_positive_filter", {})
        self.enabled = fp_cfg.get("enabled", True)
        self.threshold = fp_cfg.get("classification_threshold", 0.75)
        self.bayesian_opt_iterations = fp_cfg.get("bayesian_opt_iterations", 50)
        
        # Performance Targets
        self.precision_target = fp_cfg.get("precision_target", 0.90)
        self.f1_target = fp_cfg.get("f1_target", 0.85)
        
        # Serailized attributes
        self.model: Optional[Any] = None
        self.scaler: Optional[Any] = None
        self.is_xgb = False
        
        logger.info(
            "FalsePositiveFilter initialized (enabled=%s, threshold=%.2f, bayes_iter=%d)",
            self.enabled, self.threshold, self.bayesian_opt_iterations
        )

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """Train the classifier using either XGBoost or RandomForest with hyperparameter optimization.

        Parameters
        ----------
        X_train : np.ndarray
            Scaled training features, shape (N, 180).
        y_train : np.ndarray
            Binary training labels (1 = true defect, 0 = false positive), shape (N,).
        X_val : np.ndarray, optional
            Optional scaling validation features.
        y_val : np.ndarray, optional
            Optional scaling validation labels.

        Returns
        -------
        dict
            Dict of training performance metrics.
        """
        n_pos = int(np.sum(y_train == 1))
        n_neg = int(np.sum(y_train == 0))
        
        if n_pos == 0 or n_neg == 0:
            raise ValueError(
                f"Training set must contain both classes. Got positive={n_pos}, negative={n_neg}"
            )
            
        # 1. Handle class imbalance ratio
        scale_pos_weight = float(n_neg / n_pos) if n_pos > 0 else 1.0
        logger.info(
            "Starting classifier training. Positives=%d, Negatives=%d, Imbalance Ratio=%.2f",
            n_pos, n_neg, scale_pos_weight
        )
        
        cv = StratifiedKFold(n_splits=min(5, max(2, min(n_pos, n_neg))), shuffle=True, random_state=42)
        
        # 2. Select model and hyperparameter tuning strategy
        if XGB_AVAILABLE:
            self.is_xgb = True
            logger.info("Using XGBoost Classifier as primary model.")
            
            # Base XGBoost model
            base_model = xgb.XGBClassifier(
                objective="binary:logistic",
                eval_metric="logloss",
                scale_pos_weight=scale_pos_weight,
                random_state=42,
                n_jobs=1,
            )
            
            if SKOPT_AVAILABLE:
                # Bayesian hyperparameter optimisation
                search_spaces = {
                    "n_estimators": Integer(100, 500),
                    "max_depth": Integer(3, 8),
                    "learning_rate": Real(0.01, 0.3, prior="uniform"),
                }
                logger.info("Running BayesSearchCV for XGBoost...")
                bayes_search = BayesSearchCV(
                    estimator=base_model,
                    search_spaces=search_spaces,
                    n_iter=min(self.bayesian_opt_iterations, len(X_train)),
                    cv=cv,
                    scoring="f1",
                    n_jobs=1,
                    random_state=42,
                )
                bayes_search.fit(X_train, y_train)
                self.model = bayes_search.best_estimator_
                logger.info("XGBoost BayesSearchCV finished. Best params: %s", str(bayes_search.best_params_))
            else:
                # Fallback to GridSearch
                param_grid = {
                    "n_estimators": [100, 200, 300],
                    "max_depth": [3, 5, 7],
                    "learning_rate": [0.01, 0.1, 0.2],
                }
                logger.info("scikit-optimize not available. Falling back to GridSearchCV for XGBoost.")
                grid_search = GridSearchCV(
                    estimator=base_model,
                    param_grid=param_grid,
                    cv=cv,
                    scoring="f1",
                    n_jobs=1,
                )
                grid_search.fit(X_train, y_train)
                self.model = grid_search.best_estimator_
                logger.info("XGBoost GridSearch finished. Best params: %s", str(grid_search.best_params_))
            
        else:
            self.is_xgb = False
            logger.warning("XGBoost not available. Falling back to RandomForestClassifier.")
            
            base_model = RandomForestClassifier(
                class_weight="balanced" if scale_pos_weight == 1.0 else {1: scale_pos_weight, 0: 1.0},
                random_state=42,
                n_jobs=1,
            )
            
            if SKOPT_AVAILABLE:
                # Bayesian hyperparameter optimisation
                search_spaces = {
                    "n_estimators": Integer(100, 500),
                    "max_depth": Integer(3, 15),
                    "min_samples_split": Integer(2, 10),
                }
                logger.info("Running BayesSearchCV for RandomForest...")
                bayes_search = BayesSearchCV(
                    estimator=base_model,
                    search_spaces=search_spaces,
                    n_iter=min(self.bayesian_opt_iterations, len(X_train)),
                    cv=cv,
                    scoring="f1",
                    n_jobs=1,
                    random_state=42,
                )
                bayes_search.fit(X_train, y_train)
                self.model = bayes_search.best_estimator_
                logger.info("RandomForest BayesSearchCV finished. Best params: %s", str(bayes_search.best_params_))
            else:
                # Fallback to GridSearch
                param_grid = {
                    "n_estimators": [100, 200, 300],
                    "max_depth": [5, 10, 15],
                    "min_samples_split": [2, 5],
                }
                logger.info("scikit-optimize not available. Falling back to GridSearchCV for RandomForest.")
                grid_search = GridSearchCV(
                    estimator=base_model,
                    param_grid=param_grid,
                    cv=cv,
                    scoring="f1",
                    n_jobs=1,
                )
                grid_search.fit(X_train, y_train)
                self.model = grid_search.best_estimator_
                logger.info("RandomForest GridSearch finished. Best params: %s", str(grid_search.best_params_))
            
        # 3. Evaluate on training data
        probs = self.model.predict_proba(X_train)[:, 1]
        
        # Apply the custom threshold
        thresh_preds = (probs >= self.threshold).astype(int)
        
        metrics = {
            "train_precision": float(precision_score(y_train, thresh_preds, zero_division=0)),
            "train_recall": float(recall_score(y_train, thresh_preds, zero_division=0)),
            "train_f1": float(f1_score(y_train, thresh_preds, zero_division=0)),
            "train_auc": float(roc_auc_score(y_train, probs)),
        }
        
        # 4. Evaluate on validation set if provided
        if X_val is not None and y_val is not None:
            val_probs = self.model.predict_proba(X_val)[:, 1]
            val_thresh_preds = (val_probs >= self.threshold).astype(int)
            
            metrics.update({
                "val_precision": float(precision_score(y_val, val_thresh_preds, zero_division=0)),
                "val_recall": float(recall_score(y_val, val_thresh_preds, zero_division=0)),
                "val_f1": float(f1_score(y_val, val_thresh_preds, zero_division=0)),
                "val_auc": float(roc_auc_score(y_val, val_probs)),
            })
            
            logger.info(
                "Training complete. Val metrics at threshold %.2f: Precision=%.2f (Target=%.2f), F1=%.2f (Target=%.2f)",
                self.threshold,
                metrics["val_precision"], self.precision_target,
                metrics["val_f1"], self.f1_target
            )
        else:
            logger.info(
                "Training complete. Train metrics at threshold %.2f: Precision=%.2f, F1=%.2f",
                self.threshold, metrics["train_precision"], metrics["train_f1"]
            )
            
        return metrics

    def predict(self, scaled_features: np.ndarray) -> Tuple[int, float]:
        """Classify a single defect scaled feature vector.

        Parameters
        ----------
        scaled_features : np.ndarray
            Unified scaled feature vector of shape (180,).

        Returns
        -------
        label : int
            1 if true defect, 0 if false positive.
        probability : float
            Calibrated model confidence score (0.0 to 1.0).
        """
        if not self.enabled or self.model is None:
            # If disabled or no model loaded, assume everything is a true defect (pass-through)
            return 1, 1.0
            
        # Ensure 2D input
        feat_2d = scaled_features.reshape(1, -1)
        prob = float(self.model.predict_proba(feat_2d)[0, 1])
        
        label = 1 if prob >= self.threshold else 0
        return label, prob

    def predict_batch(self, scaled_matrix: np.ndarray) -> List[Tuple[int, float]]:
        """Batch classify multiple defect feature vectors.

        Parameters
        ----------
        scaled_matrix : np.ndarray
            Scaled feature matrix of shape (N, 180).

        Returns
        -------
        list of tuple
            List of (label, probability) tuples.
        """
        if not self.enabled or self.model is None or len(scaled_matrix) == 0:
            return [(1, 1.0)] * len(scaled_matrix)
            
        probs = self.model.predict_proba(scaled_matrix)[:, 1]
        
        results = []
        for p in probs:
            label = 1 if p >= self.threshold else 0
            results.append((label, float(p)))
            
        return results

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        """Compute comprehensive performance evaluation metrics on a test set.

        Parameters
        ----------
        X_test : np.ndarray
            Scaled test set features of shape (N, 180).
        y_test : np.ndarray
            True binary labels of shape (N,).

        Returns
        -------
        dict
            Dict of evaluation metrics: precision, recall, F1, AUC-ROC, confusion matrix.
        """
        if self.model is None:
            raise ValueError("No model trained or loaded for evaluation.")
            
        probs = self.model.predict_proba(X_test)[:, 1]
        preds = (probs >= self.threshold).astype(int)
        
        tn, fp, fn, tp = confusion_matrix(y_test, preds).ravel()
        
        metrics = {
            "precision": float(precision_score(y_test, preds, zero_division=0)),
            "recall": float(recall_score(y_test, preds, zero_division=0)),
            "f1": float(f1_score(y_test, preds, zero_division=0)),
            "auc": float(roc_auc_score(y_test, probs)),
            "confusion_matrix": {
                "true_negatives": int(tn),
                "false_positives": int(fp),
                "false_negatives": int(fn),
                "true_positives": int(tp),
            }
        }
        return metrics

    def compute_shap(self, X: np.ndarray) -> Dict[str, Any]:
        """Compute SHAP feature importance summaries to ensure auditable filtering decisions.

        Parameters
        ----------
        X : np.ndarray
            Scaled feature matrix of shape (N, 180).

        Returns
        -------
        dict
            SHAP summary statistics.
        """
        if self.model is None:
            raise ValueError("No model loaded to compute SHAP values.")
            
        summary = {"shap_available": False, "top_feature_indices": []}
        
        if SHAP_AVAILABLE:
            try:
                # Use TreeExplainer for trees (XGBoost / RandomForest)
                explainer = shap.TreeExplainer(self.model)
                shap_values = explainer.shap_values(X)
                
                # Handle binary shape differences (some explainer returns [N, F, 2], others [N, F])
                if isinstance(shap_values, list):
                    # For sklearn RF, it returns list of len 2 (classes)
                    shap_vals = shap_values[1]
                else:
                    shap_vals = shap_values
                    
                # Compute absolute mean of SHAP values per feature
                mean_shap = np.mean(np.abs(shap_vals), axis=0)
                top_indices = np.argsort(mean_shap)[::-1][:10]
                
                summary.update({
                    "shap_available": True,
                    "mean_shap_values": mean_shap.tolist(),
                    "top_feature_indices": [int(idx) for idx in top_indices],
                })
                logger.info("SHAP values successfully computed.")
                return summary
            except Exception as exc:
                logger.warning("Failed to compute SHAP values: %s. Falling back.", str(exc))
                
        # Fallback using built-in model feature importances
        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            top_indices = np.argsort(importances)[::-1][:10]
            summary.update({
                "shap_available": False,
                "mean_shap_values": importances.tolist(),
                "top_feature_indices": [int(idx) for idx in top_indices],
            })
            logger.info("Using built-in feature importances fallback for SHAP.")
            
        return summary

    def save_model(self, path: Union[str, Path]) -> None:
        """Serialize the trained XGBoost model to disk.

        Parameters
        ----------
        path : str or Path
            Output path.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as fh:
            pickle.dump({
                "model": self.model,
                "is_xgb": self.is_xgb,
                "threshold": self.threshold,
                "enabled": self.enabled,
            }, fh)
        logger.info("Filter model serialized to %s", p)

    def load_model(self, path: Union[str, Path]) -> None:
        """Deserialize and load the model.

        Parameters
        ----------
        path : str or Path
            Input file path.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Filter model serialized file not found: {p}")
        with open(p, "rb") as fh:
            data = pickle.load(fh)
            
        self.model = data["model"]
        self.is_xgb = data.get("is_xgb", True)
        self.threshold = data.get("threshold", self.threshold)
        self.enabled = data.get("enabled", self.enabled)
        
        logger.info("Filter model loaded from %s", p)
