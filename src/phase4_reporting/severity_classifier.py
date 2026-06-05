"""
severity_classifier.py — IS 13311 Severity Classification Module
==============================================================

Maps composite Vulnerability Index (VI) scores to building health condition classes
and outputs action descriptions and timelines conforming to IS 13311 structural safety standards.
"""

from __future__ import annotations

from typing import Dict, Any


def classify_vi_score(vi_score: float) -> Dict[str, Any]:
    """Map a Vulnerability Index score (0-100) to an IS 13311 condition class.

    Parameters
    ----------
    vi_score : float
        The calculated composite VI score.

    Returns
    -------
    dict
        A dictionary containing:
          - 'class': Roman numeral condition class ('I' to 'V').
          - 'label': Human-readable label (e.g. 'Class III (Significant)').
          - 'severity': Category ('Minor', 'Moderate', 'Significant', 'Severe', 'Critical').
          - 'action': Required structural remediation description.
          - 'timeline': Required response speed under the standard.
          - 'color': A recommended HEX color for report badges.
    """
    if vi_score <= 20.0:
        return {
            "class": "I",
            "label": "Class I (Minor)",
            "severity": "Minor",
            "action": "Monitor at next scheduled inspection",
            "timeline": "—",
            "color": "#2ECC71",  # Soft Green
        }
    elif vi_score <= 40.0:
        return {
            "class": "II",
            "label": "Class II (Moderate)",
            "severity": "Moderate",
            "action": "Plan maintenance",
            "timeline": "Within 6 months",
            "color": "#F1C40F",  # Soft Yellow/Amber
        }
    elif vi_score <= 60.0:
        return {
            "class": "III",
            "label": "Class III (Significant)",
            "severity": "Significant",
            "action": "Prioritise repair",
            "timeline": "Within 3 months",
            "color": "#E67E22",  # Soft Orange
        }
    elif vi_score <= 80.0:
        return {
            "class": "IV",
            "label": "Class IV (Severe)",
            "severity": "Severe",
            "action": "Immediate engineer assessment required",
            "timeline": "Within 2 weeks",
            "color": "#E74C3C",  # Soft Red
        }
    else:
        return {
            "class": "V",
            "label": "Class V (Critical)",
            "severity": "Critical",
            "action": "Halt occupancy; emergency structural review",
            "timeline": "Immediate",
            "color": "#9B59B6",  # Soft Purple
        }
