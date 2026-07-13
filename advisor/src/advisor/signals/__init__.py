"""Deterministic signal engine (SPEC M1, FR5).

Pure functions from a NodeSnapshot (+ forwarding history) to per-channel and
node-level signals. No I/O, no LLM — everything here is unit-testable.
"""

from .dataset import Dataset, OutlierResult
from .engine import ChannelSignals, NodeSignals, compute_signals

__all__ = [
    "Dataset",
    "OutlierResult",
    "ChannelSignals",
    "NodeSignals",
    "compute_signals",
]
