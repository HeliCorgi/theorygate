"""Evidence adapters for external verification engines."""

from .lean import LeanEvidenceConfig, collect_lean_evidence

__all__ = ["LeanEvidenceConfig", "collect_lean_evidence"]
