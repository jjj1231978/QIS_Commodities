"""Tests for the diagnostics helpers."""

from __future__ import annotations

import pandas as pd

from src.data.universe import Universe
from src.diagnostics import inspect_signal
from src.signals.carry import CarrySignal


class TestInspectSignal:
    def test_returns_signal_and_weight(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        result = CarrySignal(sample_config, universe).compute(synthetic_term_structures)

        # Pick a date well into the series so MA / rebalance has fired.
        date = result.weights.index[-10]
        df = inspect_signal(result, date)
        assert "signal" in df.columns
        assert "weight" in df.columns
        # At least one commodity should have a non-zero weight on that date.
        assert (df["weight"] != 0).any()

    def test_filters_by_root(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        result = CarrySignal(sample_config, universe).compute(synthetic_term_structures)

        date = result.weights.index[-10]
        cl = inspect_signal(result, date, root="CL")
        assert len(cl) == 1
        assert cl.index[0] == "CL"
