"""TheoryGate: evidence-to-claim promotion gates."""

from .evaluate import evaluate_document
from .io import load_document
from .model import Status

__all__ = ["Status", "evaluate_document", "load_document"]
__version__ = "0.1.0"
