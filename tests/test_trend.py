"""Tests for the trend (multi-lookback momentum) signal."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.universe import Universe
from src.signals.trend import TrendSignal


class TestTrendSignal:
    def test_basic_computation(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        signal = TrendSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        assert not result.weights.empty
        assert set(result.weights.columns).issubset(set(universe.roots))

    def test_uptrend_gets_long_weight(self, sample_config):
        """A clean monotonic uptrend should produce positive weights."""
        dates = pd.bdate_range("2020-01-01", "2023-12-31")
        n = len(dates)

        # Strong steady uptrend on CL, mild downtrend on others.
        up_prices = 50 + np.arange(n) * 0.05
        cl = pd.DataFrame({f"F{i}": up_prices + 0.001 * i for i in range(13)}, index=dates)
        down_prices = 100 - np.arange(n) * 0.02
        gc = pd.DataFrame({f"F{i}": down_prices + 0.001 * i for i in range(13)}, index=dates)
        # Add a couple more flat ones so each sector still has commodities.
        flat = pd.DataFrame({f"F{i}": 80 + 0.001 * i for i in range(13)}, index=dates)
        ts = {"CL": cl, "GC": gc, "NG": flat, "ZC": flat, "HG": flat}

        universe = Universe.from_config(sample_config)
        result = TrendSignal(sample_config, universe).compute(ts)

        # Late in the series the strong uptrend on CL should be long, GC short.
        late = result.weights.iloc[-1]
        assert late["CL"] > 0
        assert late["GC"] < 0

    def test_no_lookahead(self, sample_config):
        """Weights at date t should not depend on prices after t."""
        dates = pd.bdate_range("2020-01-01", "2023-06-30")
        n = len(dates)
        rng = np.random.default_rng(7)
        prices = 100 + np.cumsum(rng.standard_normal(n) * 0.5)
        ts_a = {
            root: pd.DataFrame(
                {f"F{i}": prices + 0.001 * i for i in range(13)}, index=dates
            )
            for root in ("CL", "GC", "NG", "ZC", "HG")
        }

        universe = Universe.from_config(sample_config)
        result_a = TrendSignal(sample_config, universe).compute(ts_a)

        # Now perturb only the LAST date and recompute. Weights up to the
        # second-to-last date must be unchanged.
        ts_b = {root: df.copy() for root, df in ts_a.items()}
        for root in ts_b:
            ts_b[root].iloc[-1] *= 1.5
        result_b = TrendSignal(sample_config, universe).compute(ts_b)

        common_idx = result_a.weights.index[:-1]
        pd.testing.assert_frame_equal(
            result_a.weights.loc[common_idx],
            result_b.weights.loc[common_idx],
        )
