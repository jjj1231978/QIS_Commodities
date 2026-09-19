"""Tests for the basis-momentum signal."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.universe import Universe
from src.signals.basis_momentum import BasisMomentumSignal


class TestBasisMomentumSignal:
    def test_basic_computation(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        signal = BasisMomentumSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        assert not result.weights.empty

    def test_long_short_balanced(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        signal = BasisMomentumSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        nonzero = result.weights[(result.weights != 0).any(axis=1)]
        if nonzero.empty:
            return
        for _, row in nonzero.iterrows():
            assert abs(row.sum()) < 1e-9, "Basis-momentum is dollar-neutral"

    def test_steepening_basis_gets_long_weight(self, sample_config):
        """The commodity whose basis is steepening fastest should be long."""
        dates = pd.bdate_range("2020-01-01", "2023-12-31")
        n = len(dates)

        # CL: F1-F0 spread grows monotonically over time → steepening basis.
        cl_data = {}
        for i in range(13):
            cl_data[f"F{i}"] = 100.0 + i * np.linspace(0.0, 5.0, n)
        cl = pd.DataFrame(cl_data, index=dates)
        # GC: F1-F0 spread shrinks → flattening basis.
        gc_data = {}
        for i in range(13):
            gc_data[f"F{i}"] = 200.0 + i * np.linspace(5.0, 0.0, n)
        gc = pd.DataFrame(gc_data, index=dates)
        # Two flat ones so the rank can pick a top-2 long / bottom-2 short.
        flat_a = pd.DataFrame({f"F{i}": 80 + 0.001 * i for i in range(13)}, index=dates)
        flat_b = pd.DataFrame({f"F{i}": 60 + 0.001 * i for i in range(13)}, index=dates)
        ts = {"CL": cl, "GC": gc, "NG": flat_a, "ZC": flat_b}

        universe = Universe.from_config(sample_config)
        result = BasisMomentumSignal(sample_config, universe).compute(ts)

        late = result.weights.iloc[-1]
        assert late["CL"] > 0  # steepening basis → long
        assert late["GC"] < 0  # flattening basis → short
