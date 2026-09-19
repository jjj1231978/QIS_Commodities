"""Base signal interface for all QIS strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd

from src.data.universe import Universe


@dataclass
class SignalResult:
    """Standardized output from every signal module.

    Attributes:
        weights: DataFrame (DatetimeIndex × commodity roots). Values are
            position weights. For dollar-neutral strategies, each row sums to ~0.
        signal_values: Raw signal values before portfolio construction (diagnostics).
        metadata: Strategy-specific info (contracts used, rebalance dates, etc.).
        daily_returns: Optional per-commodity per-unit-weight daily returns.
            When supplied, the backtest engine multiplies weights by this
            series instead of recomputing from term structures. Used by carry
            variants that need beta scaling or per-commodity contract pairs.
    """

    weights: pd.DataFrame
    signal_values: pd.DataFrame
    metadata: dict = field(default_factory=dict)
    daily_returns: pd.DataFrame | None = None


class BaseSignal(ABC):
    """Abstract base class for commodity QIS signals."""

    def __init__(self, config: dict, universe: Universe):
        self.config = config
        self.universe = universe

    @abstractmethod
    def compute(self, term_structures: dict[str, pd.DataFrame]) -> SignalResult:
        """Compute signal from per-commodity term structure panels.

        Args:
            term_structures: Dict mapping root symbol to DataFrame
                with DatetimeIndex and columns F0, F1, ..., F12.

        Returns:
            SignalResult with daily position weights.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for reporting."""
        ...
