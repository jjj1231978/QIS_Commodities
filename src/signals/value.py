"""Value strategy — cross-sectional mean reversion from multi-year moving average.

Rank commodities by deviation from 1-5yr MA of front-month price.
Buy cheap (below MA), sell expensive (above MA).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.signals.base import BaseSignal, SignalResult

log = logging.getLogger(__name__)


class ValueSignal(BaseSignal):
    """Cross-sectional commodity value: mean reversion to multi-year MA."""

    @property
    def name(self) -> str:
        return "value"

    def compute(self, term_structures: dict[str, pd.DataFrame]) -> SignalResult:
        """Compute value signal.

        For each commodity: deviation = (price - MA) / MA
        Rank cross-sectionally: buy the cheapest N, sell the most expensive N.
        Average signal across multiple MA windows (1-5 years).
        """
        cfg = self.config["strategies"]["value"]
        ma_windows_years = cfg["ma_windows_years"]
        n_long = cfg["n_long"]
        n_short = cfg["n_short"]
        rebalance_freq = cfg["rebalance_freq"]

        # Compute deviation from MA for each window
        deviation_by_window = []
        for window_years in ma_windows_years:
            window_days = window_years * 252
            deviations = {}

            for root in self.universe.roots:
                if root not in term_structures:
                    continue
                ts = term_structures[root]
                if "F0" not in ts.columns:
                    continue

                price = ts["F0"]
                ma = price.rolling(window_days, min_periods=window_days // 2).mean()
                dev = (price - ma) / ma
                deviations[root] = dev

            if deviations:
                deviation_by_window.append(pd.DataFrame(deviations))

        if not deviation_by_window:
            return SignalResult(weights=pd.DataFrame(), signal_values=pd.DataFrame())

        # Average deviation across MA windows
        signal_df = sum(deviation_by_window) / len(deviation_by_window)
        signal_df = signal_df.sort_index()

        # Cross-sectional ranking → weights at rebalance dates
        if rebalance_freq == "monthly":
            rebal_dates = signal_df.resample("BME").last().index
        else:
            rebal_dates = signal_df.index

        weights = self._rank_to_weights(signal_df, rebal_dates, n_long, n_short)

        # Forward-fill to daily
        weights_daily = weights.reindex(signal_df.index, method="ffill").fillna(0.0)

        return SignalResult(
            weights=weights_daily,
            signal_values=signal_df,
            metadata={"ma_windows_years": ma_windows_years, "n_long": n_long, "n_short": n_short},
        )

    def _rank_to_weights(
        self,
        signal_df: pd.DataFrame,
        rebal_dates: pd.DatetimeIndex,
        n_long: int,
        n_short: int,
    ) -> pd.DataFrame:
        """Convert cross-sectional signal to long/short weights."""
        weights = pd.DataFrame(0.0, index=rebal_dates, columns=signal_df.columns)

        for date in rebal_dates:
            if date not in signal_df.index:
                continue

            row = signal_df.loc[date].dropna()
            if len(row) < n_long + n_short:
                continue

            # Rank: most negative deviation = cheapest = buy
            ranked = row.sort_values()
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            # Gross = 1.0 (long sum = +0.5, short sum = -0.5), matching the
            # dollar-neutral convention used by carry.
            weights.loc[date, longs] = 0.5 / n_long
            weights.loc[date, shorts] = -0.5 / n_short

        return weights
