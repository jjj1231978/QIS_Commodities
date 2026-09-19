"""Tests for the backwardation-momentum signal."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.universe import Universe
from src.signals.backwardation_momentum import BackwardationMomentumSignal


class TestBackwardationMomentumSignal:
    def test_basic_computation(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        signal = BackwardationMomentumSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        assert not result.weights.empty

    def test_long_short_balanced(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        signal = BackwardationMomentumSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        nonzero = result.weights[(result.weights != 0).any(axis=1)]
        if nonzero.empty:
            return
        for _, row in nonzero.iterrows():
            assert abs(row.sum()) < 1e-9

    def test_backwardated_gets_long_weight(self, sample_config):
        """Highest F0/F12 ratio (backwardation) → long."""
        dates = pd.bdate_range("2020-01-01", "2023-12-31")

        # CL: backwardation — F0 well above F12.
        cl = pd.DataFrame(
            {f"F{i}": 100.0 - i * 1.5 + 0.0001 * np.arange(len(dates)) for i in range(13)},
            index=dates,
        )
        # GC: contango — F0 below F12.
        gc = pd.DataFrame(
            {f"F{i}": 100.0 + i * 1.5 + 0.0001 * np.arange(len(dates)) for i in range(13)},
            index=dates,
        )
        flat_a = pd.DataFrame({f"F{i}": 80 + 0.001 * i for i in range(13)}, index=dates)
        flat_b = pd.DataFrame({f"F{i}": 60 + 0.001 * i for i in range(13)}, index=dates)
        ts = {"CL": cl, "GC": gc, "NG": flat_a, "ZC": flat_b}

        universe = Universe.from_config(sample_config)
        result = BackwardationMomentumSignal(sample_config, universe).compute(ts)

        late = result.weights.iloc[-1]
        assert late["CL"] > 0  # backwardated → long
        assert late["GC"] < 0  # contango → short
