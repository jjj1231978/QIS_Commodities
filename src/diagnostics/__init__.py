"""Diagnostics helpers for inspecting `SignalResult` and backtest outputs."""

from src.diagnostics.signal_inspection import (
    inspect_signal,
    load_backtest,
    load_stats,
    load_weights,
    positions_on,
)

__all__ = [
    "inspect_signal",
    "load_backtest",
    "load_stats",
    "load_weights",
    "positions_on",
]
