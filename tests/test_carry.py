"""Tests for the carry signal."""

import numpy as np
import pandas as pd
import pytest

from src.data.universe import Universe
from src.signals.carry import CarrySignal


class TestCarrySignal:
    def test_basic_computation(self, synthetic_term_structures, sample_config):
        """Carry signal should produce weights for commodities in contango/backwardation."""
        universe = Universe.from_config(sample_config)
        signal = CarrySignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        assert not result.weights.empty
        assert result.weights.shape[0] > 0
        assert result.weights.shape[1] > 0

    def test_dollar_neutral(self, synthetic_term_structures, sample_config):
        """Weights should sum to approximately zero (dollar-neutral)."""
        universe = Universe.from_config(sample_config)
        signal = CarrySignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        # Check row sums are close to zero
        row_sums = result.weights.sum(axis=1)
        nonzero_rows = row_sums[row_sums.abs() > 1e-10]
        if len(nonzero_rows) > 0:
            assert nonzero_rows.abs().max() < 0.01

    def test_backwardation_gets_positive_weight(self, sample_config):
        """Commodities in backwardation should get positive carry weight."""
        # Create a term structure in backwardation (F0 > F3)
        dates = pd.bdate_range("2022-01-01", "2022-12-31")
        backwardated = pd.DataFrame(
            {f"F{i}": 100 - i * 2 + np.random.randn(len(dates)) * 0.1 for i in range(13)},
            index=dates,
        )
        # F0=100, F3=94 → carry = (94-100)/100 = -0.06 → negative → long position
        term_structures = {"CL": backwardated}

        # Minimal config with just CL
        cfg = sample_config.copy()
        universe = Universe.from_config(cfg)
        signal = CarrySignal(cfg, universe)
        result = signal.compute(term_structures)

        # CL should have positive weight (we go long the spread in backwardation)
        cl_weights = result.weights.get("CL", pd.Series())
        if not cl_weights.empty:
            mean_weight = cl_weights[cl_weights != 0].mean()
            assert mean_weight > 0, "Backwardated commodity should have positive weight"

    def test_signal_values_shape(self, synthetic_term_structures, sample_config):
        """Signal values should have same columns as available commodities."""
        universe = Universe.from_config(sample_config)
        signal = CarrySignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        assert not result.signal_values.empty
        # Signal values should be carry ratios (small numbers around 0)
        mean_abs = result.signal_values.abs().mean().mean()
        assert mean_abs < 0.5, f"Carry signals seem too large: {mean_abs}"
