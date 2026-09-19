"""Backwardation momentum — rank by curve slope level, adjusted for seasonality.

Cross-sectional: long backwardated markets, short contangoed markets.
Slope measured as F0 / F(12-month) to naturally adjust for seasonality.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.signals.base import BaseSignal, SignalResult

log = logging.getLogger(__name__)


class BackwardationMomentumSignal(BaseSignal):
    """Backwardation momentum: buy backwardated, sell contangoed."""

    @property
    def name(self) -> str:
        return "backwardation_momentum"

    def compute(self, term_structures: dict[str, pd.DataFrame]) -> SignalResult:
        """Compute backwardation momentum signal.

        Slope = F0 / F12 (or nearest available 12-month contract).
        When slope > 1: backwardation (front > deferred).
        When slope < 1: contango (front < deferred).

        Using F0/F12 naturally adjusts for seasonality since both contracts
        are in the same calendar month (approximately 12 months apart).

        Cross-sectional: long N most backwardated, short N most contangoed.
        """
        cfg = self.config["strategies"]["backwardation_momentum"]
        n_long = cfg["n_long"]
        n_short = cfg["n_short"]
        rebalance_freq = cfg["rebalance_freq"]

        # Compute slope for each commodity
        slopes = {}
        for root in self.universe.roots:
            if root not in term_structures:
                continue
            ts = term_structures[root]

            # Use F0 / F12 as the slope measure
            # Fall back to nearest available far contract
            far_col = None
            for i in [12, 11, 10, 9, 8]:
                col = f"F{i}"
                if col in ts.columns and ts[col].notna().sum() > 100:
                    far_col = col
                    break

            if far_col is None or "F0" not in ts.columns:
                continue

            slope = ts["F0"] / ts[far_col]
            slopes[root] = slope

        if not slopes:
            return SignalResult(weights=pd.DataFrame(), signal_values=pd.DataFrame())

        signal_df = pd.DataFrame(slopes).sort_index()

        # Rebalance
        if rebalance_freq == "monthly":
            rebal_dates = signal_df.resample("BME").last().index
        else:
            rebal_dates = signal_df.index

        # Cross-sectional ranking: most backwardated (highest slope) = long
        weights = self._rank_to_weights(signal_df, rebal_dates, n_long, n_short)
        weights_daily = weights.reindex(signal_df.index, method="ffill").fillna(0.0)

        return SignalResult(
            weights=weights_daily,
            signal_values=signal_df,
            metadata={"n_long": n_long, "n_short": n_short},
        )

    def _rank_to_weights(
        self,
        signal_df: pd.DataFrame,
        rebal_dates: pd.DatetimeIndex,
        n_long: int,
        n_short: int,
    ) -> pd.DataFrame:
        """Long most backwardated, short most contangoed."""
        # NaN, not 0.0. A rebalance that fails the guards below must leave its
        # row missing so the caller's ffill carries the previous position
        # forward; an explicit zero would instead flatten the book until the
        # next successful rebalance. Successful rows are fully written (zeros
        # for unselected names) so ffill never leaks a stale leg.
        weights = pd.DataFrame(
            float("nan"), index=rebal_dates, columns=signal_df.columns
        )

        for date in rebal_dates:
            if date not in signal_df.index:
                continue

            row = signal_df.loc[date].dropna()
            if len(row) < n_long + n_short:
                continue

            # Highest slope = most backwardated = long
            ranked = row.sort_values(ascending=False)
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            # Gross = 1.0 (long sum = +0.5, short sum = -0.5), matching the
            # dollar-neutral convention used by carry.
            weights.loc[date] = 0.0
            weights.loc[date, longs] = 0.5 / n_long
            weights.loc[date, shorts] = -0.5 / n_short

        # Rows still all-NaN are skipped rebalances — drop them so the
        # caller's ffill reaches the last successful allocation.
        return weights.dropna(how="all")
