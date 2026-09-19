"""Basis momentum — trend of futures curve slope.

Cross-sectional: fit polynomial to term structure, track slope changes.
Buy contracts with steepening basis, sell those with flattening basis.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.signals.base import BaseSignal, SignalResult

log = logging.getLogger(__name__)


class BasisMomentumSignal(BaseSignal):
    """Basis momentum: cross-sectional strategy on curve slope trend."""

    @property
    def name(self) -> str:
        return "basis_momentum"

    def compute(self, term_structures: dict[str, pd.DataFrame]) -> SignalResult:
        """Compute basis momentum signal.

        Fit a 2nd-order polynomial to each term structure (log prices vs
        contract index), use the linear coefficient as the curve "slope",
        then take the change in slope over a lookback window. Rank
        cross-sectionally: long the top-N steepening, short bottom-N.

        This follows the reference paper's preferred approach (a companion
        factor-investing note, June 2024). Set `slope_method: "front_spread"` in config
        to fall back to the simpler (F1-F0)/F0 momentum used by Boons & Prado.
        """
        cfg = self.config["strategies"]["basis_momentum"]
        poly_order = cfg["poly_order"]
        lookback = cfg["slope_lookback_days"]
        n_long = cfg["n_long"]
        n_short = cfg["n_short"]
        rebalance_freq = cfg["rebalance_freq"]
        slope_method = cfg.get("slope_method", "polynomial")

        slope_momentum = {}
        for root in self.universe.roots:
            if root not in term_structures:
                continue
            ts = term_structures[root]

            if slope_method == "front_spread":
                if "F0" in ts.columns and "F1" in ts.columns:
                    basis = (ts["F1"] - ts["F0"]) / ts["F0"]
                    slope_momentum[root] = basis - basis.shift(lookback)
            else:
                slope = _fit_curve_slope(ts, poly_order)
                slope_momentum[root] = slope - slope.shift(lookback)

        if not slope_momentum:
            return SignalResult(weights=pd.DataFrame(), signal_values=pd.DataFrame())

        signal_df = pd.DataFrame(slope_momentum).sort_index()

        # Rebalance
        if rebalance_freq == "monthly":
            rebal_dates = signal_df.resample("BME").last().index
        else:
            rebal_dates = signal_df.index

        # Cross-sectional ranking
        weights = self._rank_to_weights(signal_df, rebal_dates, n_long, n_short)
        weights_daily = weights.reindex(signal_df.index, method="ffill").fillna(0.0)

        return SignalResult(
            weights=weights_daily,
            signal_values=signal_df,
            metadata={"lookback": lookback, "n_long": n_long, "n_short": n_short},
        )

    def _rank_to_weights(
        self,
        signal_df: pd.DataFrame,
        rebal_dates: pd.DatetimeIndex,
        n_long: int,
        n_short: int,
    ) -> pd.DataFrame:
        """Rank cross-sectionally: long steepening, short flattening."""
        weights = pd.DataFrame(0.0, index=rebal_dates, columns=signal_df.columns)

        for date in rebal_dates:
            if date not in signal_df.index:
                continue

            row = signal_df.loc[date].dropna()
            if len(row) < n_long + n_short:
                continue

            # Most positive momentum = steepening = buy
            ranked = row.sort_values(ascending=False)
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            # Gross = 1.0 (long sum = +0.5, short sum = -0.5), matching the
            # dollar-neutral convention used by carry.
            weights.loc[date, longs] = 0.5 / n_long
            weights.loc[date, shorts] = -0.5 / n_short

        return weights


def _fit_curve_slope(ts: pd.DataFrame, poly_order: int) -> pd.Series:
    """Fit a polynomial to log(price) vs contract index per row and return the
    linear coefficient (the curve "slope"). Scale-invariant across commodities
    because we fit log prices.
    """
    contract_cols = [c for c in ts.columns if c.startswith("F") and c[1:].isdigit()]
    contract_cols.sort(key=lambda c: int(c[1:]))
    if len(contract_cols) < poly_order + 1:
        return pd.Series(np.nan, index=ts.index)

    x = np.arange(len(contract_cols), dtype=float)
    log_prices = np.log(ts[contract_cols].to_numpy(dtype=float))

    slopes = np.full(len(ts), np.nan)
    for i, row in enumerate(log_prices):
        valid = np.isfinite(row)
        if valid.sum() < poly_order + 1:
            continue
        coeffs = np.polyfit(x[valid], row[valid], poly_order)
        # numpy.polyfit returns highest-degree coeff first, so for degree-2
        # `[c2, c1, c0]` and the linear coefficient is at index -2.
        slopes[i] = coeffs[-2]
    return pd.Series(slopes, index=ts.index)
