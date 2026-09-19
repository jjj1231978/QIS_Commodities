"""Trend-following strategy — multi-lookback momentum on commodity futures.

Uses 1m, 3m, 6m, 12m lookback windows. Equal-weight within sector,
equal-weight across sectors.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.data.term_structure import build_ratio_adjusted_series
from src.signals.base import BaseSignal, SignalResult

log = logging.getLogger(__name__)


class TrendSignal(BaseSignal):
    """Multi-timeframe commodity trend following."""

    @property
    def name(self) -> str:
        return "trend"

    def compute(self, term_structures: dict[str, pd.DataFrame]) -> SignalResult:
        """Compute trend signal.

        For each commodity and each lookback:
            signal = sign(price / price_lagged - 1)            (binary +1/-1)
        Average across lookbacks (so the combined signal is in [-1, 1] and
        proportional to the share of windows agreeing on direction).
        Aggregate: equal-weight within sector, equal-weight across sectors.

        This mirrors the reference paper: "buying the underlying if prices have
        gone up in the past over a given period [...] or selling if prices
        have gone down". The binary form is what the paper benchmarks.
        """
        cfg = self.config["strategies"]["trend"]
        lookback_days = cfg["lookback_days"]  # [21, 63, 126, 252]
        sector_equal_weight = cfg["sector_equal_weight"]

        # Compute trend signal per commodity using ratio-adjusted series
        trend_signals = {}
        for root in self.universe.roots:
            if root not in term_structures:
                continue
            ts = term_structures[root]

            adjusted = build_ratio_adjusted_series(ts, position=0)
            if adjusted.empty:
                continue

            signals_per_lookback = []
            for lb in lookback_days:
                momentum = adjusted / adjusted.shift(lb) - 1
                signals_per_lookback.append(np.sign(momentum))

            combined = pd.concat(signals_per_lookback, axis=1).mean(axis=1)
            trend_signals[root] = combined

        if not trend_signals:
            return SignalResult(weights=pd.DataFrame(), signal_values=pd.DataFrame())

        signal_df = pd.DataFrame(trend_signals).sort_index()

        # Build weights with sector aggregation
        if sector_equal_weight:
            weights = self._sector_weighted(signal_df)
        else:
            weights = self._simple_weighted(signal_df)

        return SignalResult(
            weights=weights,
            signal_values=signal_df,
            metadata={"lookback_days": lookback_days},
        )

    def _sector_weighted(self, signal_df: pd.DataFrame) -> pd.DataFrame:
        """Equal-weight within sector, equal-weight across sectors."""
        sectors = self.universe.by_sector()
        n_sectors = len(sectors)

        weights = pd.DataFrame(0.0, index=signal_df.index, columns=signal_df.columns)

        for sector_name, commodities in sectors.items():
            sector_roots = [c.root for c in commodities if c.root in signal_df.columns]
            if not sector_roots:
                continue

            n_in_sector = len(sector_roots)
            sector_weight = 1.0 / n_sectors / n_in_sector

            for root in sector_roots:
                # Weight = sector allocation * combined-lookback signal in
                # [-1, 1]. Multiplying by the combined signal (rather than its
                # sign) means a market with mixed lookbacks holds a smaller
                # absolute position, matching the paper's lookback-averaging.
                weights[root] = signal_df[root] * sector_weight

        return weights

    def _simple_weighted(self, signal_df: pd.DataFrame) -> pd.DataFrame:
        """Equal-weight across all commodities."""
        n = signal_df.shape[1]
        return signal_df / n
