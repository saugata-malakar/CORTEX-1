"""
Configuration Loader
====================

Loads, validates, and provides structured access to the pipeline's
YAML configuration file.  Supports dot-separated key look-ups
(e.g. ``config.get('quality_gate.blur_threshold')``).

Usage::

    from src.utils.config_loader import PipelineConfig

    cfg = PipelineConfig("config/pipeline_config.yaml")
    blur_thresh = cfg.get("quality_gate.blur_threshold", default=100.0)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    import jsonschema
except ImportError:  # graceful degradation if jsonschema not installed
    jsonschema = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when the configuration fails schema validation."""


class PipelineConfig:
    """Loads and validates pipeline configuration from a YAML file.

    Parameters
    ----------
    config_path : str | Path
        Path to the YAML configuration file.
    schema_path : str | Path | None
        Optional path to a JSON-Schema file used to validate the config.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        config_path: str | Path,
        schema_path: Optional[str | Path] = None,
    ) -> None:
        self.config_path = Path(config_path).resolve()
        self._schema_path = Path(schema_path).resolve() if schema_path else None
        self._config: Dict[str, Any] = self._load_config()

        if self._schema_path is not None:
            self._validate_schema()

        logger.info("Configuration loaded from %s", self.config_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_config(self) -> Dict[str, Any]:
        """Read and parse the YAML configuration file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )
        with open(self.config_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise ValueError(
                f"Expected a YAML mapping at top level, got {type(data).__name__}"
            )
        return data

    def _validate_schema(self) -> None:
        """Validate config against a JSON-Schema (if available)."""
        if jsonschema is None:
            logger.warning(
                "jsonschema is not installed; skipping config validation."
            )
            return
        if self._schema_path is None or not self._schema_path.exists():
            logger.warning(
                "Schema file not found at %s; skipping validation.",
                self._schema_path,
            )
            return
        with open(self._schema_path, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
        try:
            jsonschema.validate(instance=self._config, schema=schema)
        except jsonschema.ValidationError as exc:
            raise ConfigValidationError(
                f"Config validation failed: {exc.message}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API — generic access
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value using dot-separated keys.

        Parameters
        ----------
        key : str
            Dot-delimited path, e.g. ``"quality_gate.blur_threshold"``.
        default : Any
            Fallback value if the key is missing.

        Returns
        -------
        Any
            The resolved value or *default*.
        """
        keys: List[str] = key.split(".")
        value: Any = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def to_dict(self) -> Dict[str, Any]:
        """Return a deep copy of the entire configuration dictionary."""
        import copy
        return copy.deepcopy(self._config)

    # ------------------------------------------------------------------
    # Public API — section-level properties
    # ------------------------------------------------------------------

    @property
    def quality_gate(self) -> Dict[str, Any]:
        """Quality gate parameters (blur threshold, exposure limits)."""
        return self._config.get("quality_gate", {})

    @property
    def enhancement(self) -> Dict[str, Any]:
        """Image enhancement parameters (CLAHE, sharpening)."""
        return self._config.get("enhancement", {})

    @property
    def stitching(self) -> Dict[str, Any]:
        """Mosaic stitching parameters (feature detector, RANSAC)."""
        return self._config.get("stitching", {})

    @property
    def gsd(self) -> Dict[str, Any]:
        """GSD calibration parameters (sensor, focal length, altitude)."""
        return self._config.get("gsd", {})

    @property
    def quantification(self) -> Dict[str, Any]:
        """Defect quantification parameters (width bins, V-Index weights)."""
        return self._config.get("quantification", {})

    @property
    def filtering(self) -> Dict[str, Any]:
        """False-positive filtering parameters (XGBoost, SHAP)."""
        return self._config.get("filtering", {})

    @property
    def reporting(self) -> Dict[str, Any]:
        """Reporting parameters (PDF template, output format)."""
        return self._config.get("reporting", {})

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"PipelineConfig(config_path={str(self.config_path)!r})"

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None
