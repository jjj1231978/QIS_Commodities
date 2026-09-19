"""Tests for the value (mean-reversion) signal."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.universe import Universe
from src.signals.value import ValueSignal


class TestValueSignal:
    def test_basic_computation(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        signal = ValueSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        assert not result.weights.empty
        # Value is cross-sectional; it ranks roots, so signal_values has same cols
        assert set(result.weights.columns).issubset(set(universe.roots))

    def test_long_short_balanced(self, synthetic_term_structures, sample_config):
        """Long and short legs each carry equal absolute weight."""
        universe = Universe.from_config(sample_config)
        signal = ValueSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        nonzero = result.weights[(result.weights != 0).any(axis=1)]
        if nonzero.empty:
            return  # Universe too small for the n_long/n_short config — skip
        for _, row in nonzero.iterrows():
            longs = row[row > 0].sum()
            shorts = row[row < 0].sum()
            # Dollar-neutral: long sum and |short sum| equal, sum to ~0.
            assert abs(longs + shorts) < 1e-9

    def test_cheap_gets_long_weight(self, sample_config):
        """A commodity well below its multi-year MA should be ranked long."""
        # Build two commodities: one below MA (cheap), one above MA (expensive).
        dates = pd.bdate_range("2018-01-01", "2023-12-31")
        n = len(dates)

        # CL: hovers around 100 then drops to 50 in last year (cheap vs MA).
        cl = pd.DataFrame(
            {
                f"F{i}": np.where(
                    np.arange(n) < n - 252,
                    100.0,
                    50.0,
                )
                + 0.001 * i
                for i in range(13)
            },
            index=dates,
        )
        # GC: hovers around 100 then jumps to 200 (expensive vs MA).
        gc = pd.DataFrame(
            {
                f"F{i}": np.where(
                    np.arange(n) < n - 252,
                    100.0,
                    200.0,
                )
                + 0.001 * i
                for i in range(13)
            },
            index=dates,
        )
        # Two more flat commodities so n_long=n_short=2 has something to rank.
        flat_a = pd.DataFrame({f"F{i}": 100 + 0.001 * i for i in range(13)}, index=dates)
        flat_b = pd.DataFrame({f"F{i}": 80 + 0.001 * i for i in range(13)}, index=dates)
        ts = {"CL": cl, "GC": gc, "ZC": flat_a, "HG": flat_b}

        cfg = dict(sample_config)
        cfg["strategies"]["value"] = {
            "enabled": True,
            "ma_windows_years": [1, 2, 3],
            "n_long": 2,
            "n_short": 2,
            "rebalance_freq": "monthly",
        }
        universe = Universe.from_config(cfg)
        result = ValueSignal(cfg, universe).compute(ts)

        # On the last date, CL should be long, GC should be short.
        last_weights = result.weights.iloc[-1]
        assert last_weights["CL"] > 0
        assert last_weights["GC"] < 0
